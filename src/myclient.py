from validate_msg import validate_integrity
from create_hash import create_hash_and_encode_msg
from sign_msg import generate_signed_msg
from verify_sign import verify_signed_msg
import threading
import sys
import re
from time import sleep
from read_config import parse_file
from read_config import get_client_load
from read_config import get_client_timeout 

#res_shuttle: dict with res_shuttle_client = signed(result, result_proof)
class Client(process):
	def setup(client_setup):
		self.rep_config, self.myclient_id, self.rep_pub_keys, self.client_pub_keys, self.my_priv_key, self.central_client, self.olymp, self.nreplicas, self.curr_config_num = client_setup
		print ("In setup and got myclient_id", myclient_id, "nreplicas", nreplicas)
		self.valid_result_proofs={}
		self.rep_res={}
		self.exp_res={}
		self.client_dict = {}
		self.client_timeout = 0
		self.is_reconfig=False
		self.num_valid_replicas=0
		self.is_op_invalid = False
		self.client_req_id=-1
		self.pending_op=""
		pass

	def receive(msg=('newconfig', new_config_num, new_config)):
		output("\n\n\n")
		output ("Client: ",myclient_id,  " :Got new config msg from Olympus with config num", new_config_num)
		crr_config_num = new_config_num
		rep_config, rep_pub_keys = new_config
		is_reconfig=True

	def receive(msg=('olymp_res_proof', result_proof, result, slot_id)):
		output ("Client: ",myclient_id,  " :Got a res proof from Olympus")
####################
		if (client_req_id > 0):
			if ((slot_id > exp_res[client_req_id-1]['slot'])):
				pass
			else:
				output ("Client: ",myclient_id,  " Slot_id of olympus msg not correct: slot_id",slot_id, "prev_req_ slot_id: ",exp_res[client_req_id-1]['slot'] )
				return
################
		if ((client_req_id in valid_result_proofs) and (not valid_result_proofs[client_req_id])):
			output ("Client: ",myclient_id,  " :Accepted Res proof from Olympus     for req_id" ,client_req_id, "with result", result, "and slot", slot_id, "for op", pending_op)
			valid_result_proofs[client_req_id] = True
			rep_res[slot_id] = result
			exp_res[client_req_id]['slot'] = slot_id
		else:
			output("Client: ",myclient_id,  "already got result proof for req_id", client_req_id)
			return


	def receive(msg=('client_result_pkg', result, replica_id, signed_result_client, client_req_id, slot_id)):
		output ("Client: ",myclient_id,  " :Got result proof pkg from replica", replica_id)
		sender_public_key_hex = rep_pub_keys[replica_id]# this cannot be a fn call, this is stored somewhere.
		orig_res_client = verify_signed_msg(sender_public_key_hex, signed_result_client)
		if not (orig_res_client):
			output ("Client: ",myclient_id,  " :Could NOT verify the identity of replica", replica_id)
		else:
			output("Client: ",myclient_id,  " :verified sign of replica", replica_id)
			result_proof = orig_res_client['result_proof']
			#maybe use slot_id and replica_id too?
			num_valid_replicas = validate_result_proof(result_proof, result)
			if not (num_valid_replicas):
				output("Client: ",myclient_id,  " :Could NOT validate result proof for req_id", client_req_id)
				output ("Client: ",myclient_id,  "Notifying Olympus")
				#what to do now?
			else:
				#handle multiple responses for same req
				output("Client: ",myclient_id,  " :Validated result proof from replica,", replica_id, "for req_id", client_req_id, "at slot_id", slot_id, "result", result) 
				if ((client_req_id in valid_result_proofs) and (not valid_result_proofs[client_req_id])):
					output ("Client: ",myclient_id,  " :Accepted Res proof from replica," , replica_id," for req_id" ,client_req_id, "with result", result, "and slot", slot_id, "for op", pending_op)
					valid_result_proofs[client_req_id] = True
					rep_res[slot_id] = result
					exp_res[client_req_id]['slot'] = slot_id
				else:
					output("Client: ",myclient_id,  "already got result proof for req_id", client_req_id)
					return


	def validate_result_proof(result_proof, result):
		output("Client: ",myclient_id,  ":trying to validate result proof")
		result_statements = result_proof['result_statements']
		#result = result_proof['result']
		result_hash = create_hash_and_encode_msg(result).digest
		valid_reps=0
		op_list=[]
		shift=0
		if len((result_statements)) < nreplicas:
			output ("Client: ", myclient_id, "Truncated res_proof of size ", len((result_statements)))
			shit=1
		for index, rstat in enumerate(result_statements):
			#output (">>",index)
			sender_public_key_hex = rep_pub_keys[index+shift]
			orig_stat=verify_signed_msg(sender_public_key_hex, rstat)
			if(orig_stat):
				#output ("Client", myclient_id, " :Verified signature of replica ", index)
				op_list.append(orig_stat['op'])
				if ((result_hash == orig_stat['digest'])):
					valid_reps+=1
					continue
				else:
					output ("Client: ", myclient_id, "Result proof error: mismatch for sender ", index)
					continue
			else:
				output ("Client: ", myclient_id, "Result proof error: Could not verify id of sender ", index)
				continue
		if (len(set(op_list)) != 1):
			output ("Client: ", myclient_id, "Invalid operation in result proof")
			is_op_invalid = True
		if (valid_reps >= (int(nreplicas/2) + 1)):
			output ("Client: ", myclient_id, "Got ", valid_reps, "valid results")
			return valid_reps
		else:
			return 0



	def generate_pseudo_rand_reqs(operation):
		ops = ["put('movie','star')", "append('movie',' wars')", "get('movie')", "slice('movie', '0:3')"]
		p1=re.search("(?<=\().*(?=\))", operation)
		load_list=[]
		if (p1):
			pair = p1.group()
			pair = pair.split(",")
			pair[1] = pair[1].strip("'")
			val = pair[1]
			val = int(val.strip()) if str.isdecimal(val) else val.strip()
			pair[0] = pair[0].strip("'")
			seed = pair[0]
			seed = int(seed.strip()) if str.isdecimal(seed) else seed.strip()
		print ("seed", seed, "val",  val)
		import random
		random.seed(seed)
		for i in range(val):
			idx = random.randint(0,3)
			load_list.append(ops[idx])
		return load_list


	def run():
#########
		output("\n\nClinent Started")
		#return

########
		config_file = sys.argv[1]
		print ("Config file", config_file)
		config(clock='Lamport')
		output("myclient_id", myclient_id)
		config = parse_file(config_file)
		myclient_load = get_client_load(config, myclient_id)
		if (not myclient_load):
			output("Client ", myclient_id, "No workload found")
			return
		print ("myclient_load[0]", myclient_load[0])
		if ("pseudorandom" in myclient_load[0]):
			output("generating pseudo load")
			myclient_load = generate_pseudo_rand_reqs(myclient_load[0])
		
		output ("\nGenerated load: ", myclient_load)
		client_timeout = get_client_timeout(config)
		client_timeout = client_timeout/1000
		output ("client-id ",myclient_id, " mytimeout in s", client_timeout, "\n\n")

		#signed_client_msg: signed<op, is_retransmit>
		op_msg={}
		#client_req_id = -1
		TIMEOUT = client_timeout
		for i in myclient_load:
			is_retransmit=0
			client_req_id +=1
			exp_res[client_req_id]={}
			exp_res[client_req_id]['slot'] =-1
			exp_res[client_req_id]['op'] = i
			valid_result_proofs[client_req_id] = False
			op_msg ['operation']= i
			op_msg['is_retransmit'] = 0
			signed_op_msg = generate_signed_msg(op_msg, my_priv_key)
			num_valid_replicas=0
			is_op_invalid = False
			pending_op = i
			output("\n\n\n")	
			output ("client ",myclient_id, "sending operation", i, "with req_id",client_req_id," to head at ", rep_config[0], "\n\n")
			send(('client_op_req', signed_op_msg, myclient_id, client_req_id), to=rep_config[0])
			if (await(valid_result_proofs[client_req_id])):
				if (is_op_invalid or (num_valid_replicas < nreplicas)):
					output ("client ",myclient_id, "Invalid operation or less than suffcient replicas in result proof, sending reconfig req to Olympus , num_valid_replicas: ", num_valid_replicas, "is_op_invalid ", is_op_invalid)
					send(('reconfig_req', myclient_id, False), to=olymp['config'])
					await((is_reconfig==True) and valid_result_proofs[client_req_id])
					is_reconfig=False
			elif timeout(TIMEOUT):
				output ("Client", myclient_id, "timed out waiting for operation", i, "with req-id", client_req_id)
				is_retransmit=1
				op_msg['is_retransmit'] = 1
				signed_op_msg = generate_signed_msg(op_msg, my_priv_key)
				for idx in rep_config:
					output ("client ",myclient_id, "RESEND op_req", i, "with req_id",client_req_id," to rep ", idx, "at ", rep_config[idx])
					send(('client_op_req', signed_op_msg, myclient_id, client_req_id), to=rep_config[idx])
				if (await(valid_result_proofs[client_req_id])):
					output ("canceling timer")
				elif timeout(TIMEOUT+5):
					output ("Client", myclient_id, "timed out again and seding reconfig reqs to Olympus")
					#ask for reconfig from olympus
					send(('reconfig_req', myclient_id, False), to=olymp['config'])
					if (await((is_reconfig==True) and valid_result_proofs[client_req_id])):
						is_reconfig=False
					elif timeout(TIMEOUT+10):
						if (is_reconfig):
							is_reconfig=False
							output ("Client", myclient_id, "Timedout waiting for new config  and did not recevive a valid result proof for ", client_req_id, "Retry with new config")
							sleep(5)
						else:
							output ("Client", myclient_id, "Not even recnfigured, Don't know what to do now")
							await(0)
							return
							
						#sys.exit()
			sleep(1)
		output ("client ",myclient_id,  "Sending to replicas done, now sending results to central config")
		send(('client_verify_res', rep_res, exp_res, myclient_id), to=central_client)
		await(0)
