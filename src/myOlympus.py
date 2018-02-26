import sys
cdef = import_da('rep_classes')
cldef = import_da('client')
ccldef = import_da('central_client')
#olympdef = import_da('olympus')
from validate_msg import validate_integrity
from create_hash import create_hash_and_encode_msg
from sign_msg import get_key_pair
from read_config import parse_file
from read_config import get_num_clients
from read_config import get_num_replicas
from verify_sign import verify_signed_msg
from helpers import are_keys_unique





from itertools import combinations
from collections import OrderedDict
from sign_msg import generate_signed_msg
from time import sleep



class Olympus(process):
	def setup(olymp_setup):
		self.nreplicas, self.nclients, self.rep_config, self.rep_pub_keys, self.client_config, self.client_pub_keys, self.olymp_keys, self.curr_config_num=olymp_setup
		#****************DON"T FORGET TO RESET THEM************************#
		self.in_reconfig = False #are we in the middle of a reconfig
		self.quorum_candidates={}
		self.quorum={}
		self.caughtup_hash={}
		self.rep_running_state={}
		self.client_res_shuttle={}
		self.recent_client_req_map={}
		self.mytimeout=0
		self.num_wedge_responses=0
		self.is_client_ready={}
		self.longest_slot_len=0
		self.curr_longest_slot_len=0
		pass

	def send_to_all(config, is_replica):
		for idx in config:
			wedge_msg={}
			wedge_msg['msg'] = 'wedge_req'
			signed_wedge_msg = generate_signed_msg(wedge_msg, olymp_keys['priv_key'])
			send(('wedge_req', signed_wedge_msg), to=config[idx])

	def receive(msg=('wedge_resp', sender_id, history)):
		output("\n\n")
		#so_history is a dictionary of dictionaries {slot, operation}
		output ("Olympus:      Got a wedge_resp from replica", sender_id)
		num_wedge_responses+=1
		so_history = validate_history(sender_id, history)
		if (so_history is not None):
			quorum_candidates[str(sender_id)] = so_history
			output ("Olympus:      Validated history for replica", sender_id)
		else:
			output ("Olympus:      Could NOT validate history for replica", sender_id)

	def receive(msg=('reconfig_req', sender_id, isreplica)):
		output("\n\n")
		if (not isreplica):
			if (not in_reconfig):
				output ("Olympus:      Got a reconfig_req from client," , sender_id, "sending wedged reqs to all replicas")
				in_reconfig=True
				is_client_ready[sender_id]=True
				send_to_all(rep_config, True)
			else:
				output ("Olympus:      Got a reconfig_req from client," , sender_id, "already in reconfig")
				is_client_ready[sender_id]=True
		else:
			if (not in_reconfig):
				in_reconfig=True
				output ("Olympus:      Got a reconfig_req from replica", sender_id, "sending wedged reqs to all replicas")
				send_to_all(rep_config, True)
			else:
				output ("Olympus:      Got a reconfig_req from replica", sender_id," already in reconfig , ignoring")

	def receive(msg=('caughtup_req', run_hash, signed_res_stat_map, sender_id)):
		#do some sort of sign verification here
		output ("Olympus:      Got a caughtup msg from replica," , sender_id, "with hash", run_hash)
		if (run_hash):
			caughtup_hash[sender_id] = run_hash
		else:
			output ("Olympus-WARNING:      Got an empty caughtup msg from replica," , sender_id)
			caughtup_hash[sender_id] = None
		for client_id, req_res_stat in signed_res_stat_map.items():
			client_res_shuttle.setdefault(client_id, [])
			#append result_stat, slot_id, sender
			client_res_shuttle[client_id].append((req_res_stat[0], req_res_stat[1], req_res_stat[2]))
		
	def receive(msg=('running_state', run_state, sender_id)):
		output ("Olympus:      Got a run state",  run_state, ", from replica," , sender_id)
		rep_running_state[sender_id] = run_state

	def receive(msg=('recent_client_req_map', recent_client_rq_map, sender_id)):
		output ("Olympus:      Got req_map from replica", sender_id)	
		recent_client_req_map[sender_id]=recent_client_rq_map

	def validate_order_proof(order_proof, next_slot_id, sender_id):
		output("Olympus:      Trying to validate order proof for rep", sender_id, "at slot ", next_slot_id)
		order_statements = order_proof['order_statements']
		if (len(order_statements) != (sender_id+1)):
			output ("Olympus      :Length of order proof not correct")
			return None	
		operation = order_proof['op']
		slot_id = order_proof['slot_id']
		if (slot_id != next_slot_id):
			output("Olympus:      Unexpected slot id in history from replica", sender_id)
			return None
		#output("slot_id", slot_id, "op:", operation)
		for index, ostat in enumerate(order_statements):
			#output (">>",index, ostat)
			sender_public_key_hex = rep_pub_keys[index]
			orig_stat=verify_signed_msg(sender_public_key_hex, ostat)
			if(orig_stat):
				#output ("Olympus:     Verified signature of replica ", index)
				#output("validated order proof, type orig_stat", type(orig_stat), "sid", orig_stat['slot_id'], "op",orig_stat['op'])
				if ((slot_id == orig_stat['slot_id']) and (operation == orig_stat['op'])):
					continue
				else:
					output ("Olympus:      Order Proof validation mismatch for replica ", index, "from sender", sender_id)
					return None
			else:
				output ("Olympus:      Order Proof validation Could not verify id of replica ", index, "from sender", sender_id)
				return None

		return (slot_id, operation)


	def validate_history(sender_id, history):
		so_history={}
		#empty hist is not invalid
		if (not history):
			return so_history
		next_slot_id=0
		#so_history['slot']=None
		#so_history['operation']=None
		output("Olympus:      Trying to validate history for replica ", sender_id)
		for o_proof in history:
			hist = validate_order_proof(o_proof, next_slot_id, sender_id)
			if (not hist):
				return None
			else:
				so_history[next_slot_id] = {'slot' : hist[0], 'operation' : hist[1]}
				next_slot_id += 1
				continue
		return so_history


	def do_they_agree(hist1, hist2):
		#hist1 = quorum_candidates[rep1]
		#hist2 = quorum_candidates[rep2]
		output("Olympus:      len hist1", len(hist1)," and len hist2", len(hist2))
		min_len = min(len(hist1), len(hist2))
		# we can do a contiguous for loop for this as hist is contiguous
		for i in range(min_len):
			if ((hist1[i]['slot'] == hist2[i]['slot']) and (hist1[i]['operation'] == hist2[i]['operation'])):
				continue
			else:
				output("Olympus:      replicas disagree")
				return False
		return True

	def check_consistency(qc):
		#a list of dictionaries
		if (not qc):
			output("Olympus:      Empty quorum")
			return False
		output("Olympus:      Checking consistency of quorum", qc)
		qc_hist = list(quorum_candidates[k] for k in qc)#list of so_histories
		qc_hist.sort(key=len)
		for i in range(0,len(qc_hist)-1):
			if do_they_agree(qc_hist[i], qc_hist[i+1]):
				continue
			else:
				output("Olympus:      Could not verify consistency of quorum ",qc)
				return False
		output("Olympus:      Verified consistency of quorum ",qc)
		return True


	def get_diff_op(lh, dict2):
		#all s,o pairs which dict2 does not have
		diff = { k : lh[k] for k in set(lh) - set(dict2) if k in lh}
		diff_slots = [int(k) for k in set(lh) - set(dict2) if k in lh]
		diff_slots.sort()
		op_seq=[]
		for k in diff_slots:
			op_seq.append(lh[k]['operation'])
		return op_seq
		
	def check_hash_consistency(quorum):
		#there may be an empty entry
		if (None in caughtup_hash.values()):
			output("Olympus:      Got Empty run hash and consistency check failed for quorum", quorum)
			return False
		if (len(set(caughtup_hash.values()))==1):
			output("Olympus:      Verified hash consistency of quorum ",quorum)
			return True
		else:
			output("Olympus:      Could not check hash consistency")
			return False


	def check_quorum_state(quorum):
		if (not quorum):
			output("Olympus:      Empty quorum")
			return False
		output("Olympus:      Checking running state of quorum ", quorum)
		qdict = dict((k, quorum_candidates[k]) for k in quorum)
		qdict_sorted = OrderedDict(sorted(qdict.items(), key=lambda t: len(t[1])))
		lh = list(qdict_sorted.items())[-1]
		output("Olympus:      Longest history replica in quorum  ", quorum, "is", lh[0], "with len ", len(lh[1]))
		curr_longest_slot_len = len(lh[1])
		#request recent_client_req_map from lh replica
		recent_client_req_map={}
		output("Olympus:      Sending recent_req_map to replica ", int(lh[0]))
		send(('recent_req_map',), to=rep_config[int(lh[0])])
		await(len(recent_client_req_map)>0)
		client_res_shuttle={}
		caughtup_hash={}
		for rep in qdict_sorted:
			catch_seq = get_diff_op(lh[1], qdict_sorted[rep])
			output("Olympus:      Sending catchup seq", catch_seq ,"to replica", rep)
			send(('catchup', catch_seq, recent_client_req_map), to=rep_config[int(rep)])
		#wait for response
		TIMEOUT = 10
		if (await(len(caughtup_hash) == int(nreplicas/2) + 1)):
			return check_hash_consistency(quorum)
		elif timeout(TIMEOUT):
			output("Olympus:      Timed out waiting for a quorum of hashes")
			return False 
			

	def is_state_valid(quorum):
		output("Olympus:      Trying to validate quorum state")
		for rep in quorum:
			rep_running_state={}
			output("Olympus:      Sending get_running_state to replica", int(rep))
			send(('get_running_state',), to=rep_config[int(rep)])
			TIMEOUT = 10
			if (await(len(rep_running_state) > 0)):
				rep_running_state_sort = OrderedDict(sorted(rep_running_state[int(rep)].items()))
				result_msg_hash = create_hash_and_encode_msg(rep_running_state_sort)
				output("Olympus:      hash of sorted state ", rep_running_state_sort, "is ", result_msg_hash.digest)
				if (result_msg_hash.digest == caughtup_hash[int(rep)]):
					return True
				else:
					output("Olympus:      Could not validate running state of replica", rep, "trying next")
					output("Olympus:      Expected ", result_msg_hash.digest, " but got ", caughtup_hash[int(rep)])
					continue
			elif timeout(TIMEOUT):
				output("Olympus:      Timed out waiting for a running state")
				continue
		output("Olympus:      Fatal, Could not validate any state in quorum")
		return False


	def select_quorum():
		qdict_sorted = OrderedDict(sorted(quorum_candidates.items(), key=lambda t: len(t[1]), reverse=True))
		key_list = list(qdict_sorted.keys())
		output("Olympus:      Sorted list: ", key_list)
		output("Olympus:      Rep hist lens :", [(v, len(qdict_sorted[v])) for v in key_list])
		qc_list = list(combinations(key_list, int(nreplicas/2) + 1))
		for qc in qc_list:
			output("Olympus:      Trying quorum ", qc)
			if (check_consistency(qc) and check_quorum_state(qc)):
				return qc
			else:
				output("\n\n")
				continue
				
		output("Olympus:      Fatal, Could not find a quorum")
		return None

	def kill_past_config():
		output("Olympus:      Sending kill msgs to replicas")
		for idx in rep_config:
			send(('kill_self', curr_config_num), to=rep_config[idx]) 
			end(rep_config[idx])

	def notify_clients():
		output("Olympus:      Send new_configs to clients with config_num", curr_config_num)
		for idx in client_config:
			output("Olympus:      Send new_configs to client", idx," with config_num", curr_config_num)
			new_config=(rep_config, rep_pub_keys)
			send(('newconfig', curr_config_num, new_config), to=client_config[idx])


	def check_client_ready(client_id):
		output("Olympus:      Checking if client", client_id, "is ready")
		if not client_id in is_client_ready:
			is_client_ready[client_id]=False
		TIMEOUT = 12
		if (await(is_client_ready[client_id])):
			output("Olympus:      Client", client_id, "is ready")
			return 1
		elif timeout(TIMEOUT):
			output("Olympus:      Timed out waiting for client", client_id)
			return 0


	#client_res_shuttle[client_id].append((req_res_stat[0], req_res_stat[1], req_res_stat[2]))
	#append result_stat, slot_id, sender
	def send_res_proof_to_clients():
		output("Olympus:      Res proofs for clients")
		for client_id in client_res_shuttle:
			if (not check_client_ready(client_id)):
				continue
			output("Olympus:      Checking res proofs for client", client_id)
			res_stats = client_res_shuttle[client_id]
			result_hash_list=[]
			result_digest=""
			result=""
			result_proof={}
			for tup in res_stats:	
				slot_id=tup[1]
				orig_stat=verify_signed_msg(rep_pub_keys[tup[2]], tup[0])
				if (orig_stat):
					result = orig_stat['result']
					res_op = orig_stat['op']
					res_slot = orig_stat['slot_id']
					result_digest = create_hash_and_encode_msg(result).digest
					result_hash_list.append(orig_stat['digest'])
					output("Olympus:      Client: ",client_id,"Got result ",result,"from rep",tup[2], "at slot" , tup[1])
					output("Olympus:      Client: ",client_id,"Orig_res_stat: result ",result,"from rep",tup[2], "at slot" , res_slot, "and op", res_op)
			if (len(result_hash_list) == (int(nreplicas/2) + 1) and (len(set(result_hash_list)) == 1) and (result_digest == result_hash_list[0])):
				output("Olympus:      Res proof Validated and Sending res proofs to client",client_id)
				result_proof['result_statements'] = result_hash_list
				send(('olymp_res_proof', result_proof, result, longest_slot_len + slot_id), to=client_config[client_id])
			else:
				output("Olympus:      Did not find a quorum of result proof for client", client_id)

	
	def init_new_config():
		output("\n\n\n")
		#config(channel = {'reliable', 'fifo'})
		curr_config_num+=1
		longest_slot_len += curr_longest_slot_len	
		output("Olympus:      Generating new config with config num", curr_config_num)
		rep_config, rep_pub_keys, priv_keys, olymp_config = [{}, {}, {}, {}]
		for i in range (nreplicas):
			key_pair = get_key_pair()
			priv_keys[i] = key_pair.priv_key
			rep_pub_keys[i] = key_pair.public_key_hex

		output("Olympus:      Creating replicas again")
		for i in range (nreplicas):
			name="Replica"
			name+=str(i)
			if (i == 0):
				output (">>at dummy head")
				#dummy=new(Dummy, at='Head')
				#setup(dummy,(4,5))
				#start(dummy)
				ps_head = new(cdef.Gen_Replica, at='Head')
				output ("head created")
				rep_config[i]=ps_head
			elif (i == nreplicas-1):
				output ("tail")
				ps_tail = new(cdef.Gen_Replica, at='Tail')
				output ("tail created")
				rep_config[i]=ps_tail
			else:
				output (name)
				others = new(cdef.Gen_Replica, at=name)
				output (name," created")
				rep_config[i]=others

		output("Olympus:      Distribute keys to replicas again")
		olymp_config['config']=self
		olymp_config['pub_keys'] = olymp_keys['pub_key']
		new_values = {}
		for i in range (nreplicas):
			new_values['curr_config_num']= curr_config_num
			new_values['mydict'] = next (iter (rep_running_state.values()))
			new_values['longest_slot_len'] = longest_slot_len
			if (i == 0):
				print("\nat HEAD\n")
				rep_setup=(rep_config, i, rep_pub_keys, client_config, client_pub_keys, priv_keys[i], True, False, olymp_config, new_values)
				setup(ps_head, (rep_setup,))
				start(ps_head)
			elif (i == nreplicas-1):
				print ("\nAt tail\n")
				rep_setup=(rep_config, i, rep_pub_keys, client_config, client_pub_keys, priv_keys[i], False, True, olymp_config, new_values)
				setup(ps_tail, (rep_setup,))
				start(ps_tail)
			else:
				rep_setup=(rep_config, i, rep_pub_keys, client_config, client_pub_keys, priv_keys[i], False, False, olymp_config, new_values)
				setup(rep_config[i], (rep_setup,))
				start(rep_config[i])

		quorum_candidates, quorum, caughtup_hash, rep_running_state, client_res_shuttle, recent_client_req_map, is_client_ready = [{}, {},{},{},{},{},{}]
		in_reconfig, num_wedge_responses=[False, 0]
		output("Olympus:      Init config ",curr_config_num, "DONE")

	
	def build_quorum():
		quorum = select_quorum()
		if (quorum):
			output("Olympus:      Selected quorum", quorum)
			if(is_state_valid(quorum)):
				output("Olympus:      Validated state in quorum", next (iter (rep_running_state.values())))
				kill_past_config()
				#################################
######################
				send_res_proof_to_clients()
				init_new_config()
				notify_clients()
				in_reconfig= False
				output("Olympus:     New Config DONE \n")
				return 1
				#notify client , need to establish sorted order here as that is how order proof is checked
			else:
				output("Olympus:      Fatal, Could not validate any state in quorum")	
				return 0
		else:
			print("Olympus:      Fatal, Could not select quorum")
			return 0

	def run():
		mytimeout = 7
		TIMEOUT = mytimeout
		config(channel = {'reliable', 'fifo'})
		config(clock='Lamport')
		output("Olympus:      Started")
##############
		'''	sleep(1)
		output(">>Olympus:      Trying to create dummy")
		#kill_past_config()
		output("Olympus:      Trying to create dummy")
		dummy=new(Dummy, num=1, at='Head')
		output("Olympus:      Dummy created DOne ")
		setup(dummy,(4,5))
		start(dummy)
		'''
##############


		while(1):
			while (not in_reconfig):
				--wait
			
			if (await(num_wedge_responses  == int(nreplicas))):
				output("\n\n")
				if (len(quorum_candidates) < (int(nreplicas/2) + 1)):
					 output("Olympus:     Not enough replicas to build quorum")
				else:
					output("Olympus:      Got ", len(quorum_candidates) ," number of replies")
					


					if (not build_quorum()):
						output("Olympus:      Could not build quorum")
						return
			elif timeout(TIMEOUT):
				output("Olympus:      Timedout waitiing for wedged responses, got ",len(quorum_candidates)," responses")
				if (len(quorum_candidates) < (int(nreplicas/2) + 1)):
					output("Olympus:     Not enough replicas to build quorum")
				else:
					if (not build_quorum()):
						output("Olympus:      Could not build quorum")
						return





























def main():
	config(channel = {'reliable', 'fifo'})
	config(clock='Lamport')
	config_file = sys.argv[1]
	print ("Config file", config_file)

######################
	'''
	output(">>Main:      Trying to create dummy")
	#kill_past_config()
	dummy=new(Dummy, num=1, at='Head')
	output(">> Main:      DOne ")
	setup(dummy,(4,5))
	start(dummy)



	dummy=new(Dummy2, num=1, at='Rep1')
	output(">> Main at Rep1:      DOne ")
	setup(dummy,(4,5))
	start(dummy)


	dummy=new(Dummy2, num=1, at='Tail')
	output(">> Main at Tail:      DOne ")
	setup(dummy,(4,5))
	start(dummy)

	dummy=new(Dummy2, num=1, at='Client0')
	output(">> Main at Rep1:      DOne ")
	setup(dummy,(4,5))
	start(dummy)


	dummy=new(Dummy2, num=1, at='Central_client')
	output(">> Main at Tail:      DOne ")
	setup(dummy,(4,5))
	start(dummy)

	olymp = new(Olympus, num=1)	
	olymp_setup = (2, 3, 4, 5, 6, 7, 8, 0)
	setup(olymp, (olymp_setup,))
	start(olymp)
	output("Created Olymous DOne >>\n")
	return
	'''
#######################
	# create n process
	config = parse_file(config_file)

	nreplicas= get_num_replicas(config)
	nclients = get_num_clients(config)

	output("Olympus: nreplicas", nreplicas, "nclients",  nclients)
 
	rep_config = {}
	client_info = {}	
	myreplica_id = 999
	#keys = {}
	priv_keys={}
	client_priv_keys={}
	client_config={}
	client_pub_keys={}
	rep_pub_keys={}
	olymp_keys={}
	olymp_config={}
	am_I_head= True
	am_I_tail = False

	client_info['config'] = client_config
	client_info['pub_key'] = client_pub_keys

	key_pair = get_key_pair()
	olymp_keys['priv_key'] = key_pair.priv_key 
	olymp_keys['pub_key'] = key_pair.public_key_hex
#######	####
	olymp = new(Olympus, num=1)
	#olymp=123
######	###
	olymp_config['config'] = olymp
	olymp_config['pub_keys'] =  key_pair.public_key_hex
	for i in range(nclients):
		key_pair = get_key_pair()
		client_priv_keys[i] = key_pair.priv_key
		client_pub_keys[i] = key_pair.public_key_hex	

	for i in range(nclients):
		name="Client"
		name+=str(i)
		client_config[i] = new(cldef.Client, at=name)

	for i in range (nreplicas):
		key_pair = get_key_pair()
		priv_keys[i] = key_pair.priv_key
		rep_pub_keys[i] = key_pair.public_key_hex

	are_keys_unique(priv_keys)
	are_keys_unique(rep_pub_keys)

	output("Olympus: Creating replicas")
	for i in range (nreplicas):
		name="Replica"
		name+=str(i)
		#rep_config[i] = name
		#rep_config['replica_id'] = i   
		#output (rep_config.items())
		if (i == 0):
			output ("head")
			'''
#################
			ps_head = new(Dummy, num=1, at="Head")
			rep_config[i]=ps_head
			continue
			'''
####################
			ps_head = new(cdef.Gen_Replica, at="Head")
			rep_config[i]=ps_head
		elif (i == nreplicas-1):
			output ("tail")
			ps_tail = new(cdef.Gen_Replica, at="Tail")
			rep_config[i]=ps_tail
		else:
			others = new(cdef.Gen_Replica, at=name)
			output("type others", type(others), "others", others)
			rep_config[i]=others

	output("Olympus: >>Distribute keys to replicas")
	new_values={}
	for i in range (nreplicas):
		new_values['curr_config_num']= 0
		new_values['mydict'] = {}
		new_values['longest_slot_len'] = 0 
		if (i == 0):
			print("\nat HEAD\n")
######################
			'''
			setup(ps_head, (4,5))
			start(ps_head)	
			continue
			'''
#####################
			rep_setup=(rep_config, i, rep_pub_keys, client_config, client_pub_keys, priv_keys[i], True, False, olymp_config, new_values)
			setup(ps_head, (rep_setup,))
			start(ps_head)
		elif (i == nreplicas-1):
			print ("\nAt tail\n")
			rep_setup=(rep_config, i, rep_pub_keys, client_config, client_pub_keys, priv_keys[i], False, True, olymp_config, new_values)
			setup(ps_tail, (rep_setup,))
			start(ps_tail)
		else:
			rep_setup=(rep_config, i, rep_pub_keys, client_config, client_pub_keys, priv_keys[i], False, False, olymp_config, new_values)
			setup(rep_config[i], (rep_setup,))
			start(rep_config[i])


	output("Olympus: Distribute keys to replicas DONE")

	central_client = new(ccldef.Central_Client, at="Central_client")
	setup(central_client, (nclients, client_config))
	start(central_client)

	for i in range (nclients):
		client_setup=(rep_config, i, rep_pub_keys, client_pub_keys, client_priv_keys[i], central_client, olymp_config, nreplicas, 0)
		setup(client_config[i], (client_setup,))
		start(client_config[i])

	olymp_setup = (nreplicas, nclients, rep_config, rep_pub_keys, client_config, client_pub_keys, olymp_keys, 0)
######remove commenting
	setup(olymp, (olymp_setup,))
	start(olymp)
	await(0)	
####

######################
	'''
	sleep(4)	
	output(">>Main:      Trying to create dummy")
	#kill_past_config()
	dummy=new(Dummy, num=1, at='Head')
	output(">> Main:      DOne ")
	setup(dummy,(4,5))
	start(dummy)
	'''
###########################

	return
