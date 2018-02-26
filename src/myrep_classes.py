from validate_msg import validate_integrity
from create_hash import create_hash_and_encode_msg
from sign_msg import generate_signed_msg
from verify_sign import verify_signed_msg
from read_config import parse_file
from read_config import get_rep_fail_triggers
from read_config import get_num_clients
from read_config import get_non_head_timeout
from read_config import get_head_timeout
from collections import deque
from collections import OrderedDict
from time import sleep
import os
import logging
helpers = import_da('validate_proofs')

import copy
import threading
import re
import sys

class Gen_Replica(process, helpers.Helpers):
	def setup(rep_setup):
		self.rep_config, self.myreplica_id, self.rep_pub_keys, self.client_config, self.client_pub_keys, self.my_priv_key, self.am_I_head, self.am_I_tail, self.olymp_config, self.new_values = rep_setup
		self.curr_config_num = new_values['curr_config_num']
		self.mydict = new_values['mydict']
		self.longest_slot_len = new_values['longest_slot_len']
		self.rep_fail_triggers={}
		self.pending_failures={}
		self.num_clients=0
		self.pending_failures['fwd_shuttle']=[]
		self.pending_failures['res_shuttle']=[]
		self.pending_failures['wedge_msg']=[]
		self.pending_failures['only_client'] = []
		self.pending_slot_failure=False
		self.client_msg = {}
		self.req_slot_map={}
		self.next_slot_id=0
		self.res_proof_cache={}
		self.curr_handling_req =()
		self.mytimeout = 0
		self.catchup_msg_num=-1
		self.get_run_state_msg_num=-1
		self.wedge_req_msg_num=-1
		self.new_config_msg_num=0
		self.mode=0
		self.history=[]
		self.recent_client_req_map=deque(len(client_config)*[0], len(client_config))
		self.signed_res_stat_map={}
		self.pseudo_dict={}


	def receive(msg=('wedge_req', signed_wedge_msg)):
		output("\n\n")
		output("Replica", myreplica_id, " :Got wedge req from Olympus")
		wedge_req_msg_num += 1
		failure = super().check_for_failures(-1, 'wedge_req', wedge_req_msg_num, rep_fail_triggers)
		if failure and any(x in failure for x in ["sleep", "crash", "extra_op", "drop", "increment_slot"]):
			pending_fail = apply_immediate_failure(mydict, failure, False)
			if (pending_fail == "drop"):
				return
		elif (failure):
			output ("Replica", myreplica_id, " :Found failure", failure, "for wedge_req  at msg num ", wedge_req_msg_num)
			super().update_relevant_failure(failure, "wedge_req", -1, wedge_req_msg_num, pending_failures)
		orig_msg=verify_signed_msg(olymp_config['pub_keys'], signed_wedge_msg)
		if orig_msg:
			send_hist =  copy.deepcopy(history)
			mode = 2
			if (len(pending_failures['wedge_msg']) != 0):
				next_failure = pending_failures['wedge_msg'].pop(0)
				output("Replica", myreplica_id, "next_fail", next_failure)
				if ("truncate_history" in next_failure[0]):
					p1=re.search("(?<=\().*(?=\))", next_failure[0])
					pair = p1.group()
					tr_len = int(pair.strip()) 
					output("Replica", myreplica_id, " :Found failure truncate hist with len", tr_len)
					if (tr_len <= len(send_hist)):
						for i in range(0,tr_len):
							send_hist.pop()	
			output("Replica", myreplica_id, " :Sending history with hist_len",len(send_hist))
			send(('wedge_resp', myreplica_id, send_hist), to=olymp_config['config'])
		else:
			output("Replica", myreplica_id, " :Could not verify Olympus identity")


	def receive(msg=('recent_req_map',)):
		output("\n\n")
		output("Replica", myreplica_id, " :Got recent_req_map msg from Olympus")
		output("Replica", myreplica_id, " :Sending map", recent_client_req_map, "to Olympus")
		send(('recent_client_req_map', recent_client_req_map, myreplica_id), to=olymp_config['config'])

	def receive(msg=('kill_self', config_num)):
		output("\n\n")
		output("Replica", myreplica_id, " :Got kill self from Olympus")
		logging.shutdown()
		os._exit(-1)
		output("Replica", myreplica_id, " Killing failed")

	
	def receive(msg=('catchup', catch_seq, client_req_map)):
		output("\n\n")
		output("Replica", myreplica_id, " :Got catchup req from Olympus catchup len", len(catch_seq), "catch_seq", catch_seq)
		output("Replica", myreplica_id, " :client_req map is", client_req_map)
		catchup_msg_num+=1
		pseudo_dict = {}
		pseudo_dict = copy.deepcopy(mydict)
		pseudo_next_slot_id = copy.deepcopy(next_slot_id)
		pseudo_signed_res_stat_map = copy.deepcopy(signed_res_stat_map)
		failure = super().check_for_failures(-1, 'catch_up', catchup_msg_num, rep_fail_triggers)
		if failure and any(x in failure for x in ["sleep", "crash", "extra_op", "drop", "increment_slot"]):
			pending_fail = apply_immediate_failure(mydict, failure, False)
			pending_fail = apply_immediate_failure(pseudo_dict, failure, True)
			if ("drop" in pending_fail):
				return
		elif (failure):
			output ("Replica", myreplica_id, " :Found failure", failure, "for catchup at msg num ", catchup_msg_num)
			super().update_relevant_failure(failure, "catch_up", -1, catchup_msg_num, pending_failures)
		#(client_id, order_proof['slot_id'], order_proof['operation'])
		if catch_seq:
			client_queue = next (iter (client_req_map.values()))
			lenq = len(client_req_map)
			#hope is that reqs get appended in slot order in this queue and only num_client reqs are outstanding at a time
			[client_queue.pop() for i in range(lenq - len(catch_seq))]
			output("Replica", myreplica_id, " :client_req map after popping is ", client_queue)
			for op in catch_seq:
				result=apply_operation(pseudo_dict, op)
				#what about?
				#history.append(copy.deepcopy(order_proof))
                                #recent_client_req_map
				cli_id = client_queue.pop()
				output("Client_id ", cli_id)
				result_msg_hash = create_hash_and_encode_msg(result)
				result_stat = {'result_tag':"result", 'slot_id': pseudo_next_slot_id, 'op':op, 'result':result, 'digest':result_msg_hash.digest}
				signed_result_stat = generate_signed_msg(result_stat, my_priv_key)
				pseudo_signed_res_stat_map[cli_id] = (signed_result_stat, pseudo_next_slot_id, myreplica_id)
				pseudo_next_slot_id += 1

		mydict_sorted = OrderedDict(sorted(pseudo_dict.items()))
		run_hash = create_hash_and_encode_msg(mydict_sorted)
		output("Replica", myreplica_id, " :Sending caughtup msg to Olumpus with hash of \n", mydict_sorted, " is \n", run_hash.digest )
		send(('caughtup_req', run_hash.digest, pseudo_signed_res_stat_map, myreplica_id), to=olymp_config['config'])

	def receive(msg=('get_running_state',)):
		output("\n\n")
		output("Replica", myreplica_id, " :Got get_running_state msg from Olympus")
		get_run_state_msg_num += 1
		failure = super().check_for_failures(-1, 'get_run_state', get_run_state_msg_num, rep_fail_triggers)
		if failure and any(x in failure for x in ["sleep", "crash", "extra_op", "drop", "increment_slot"]):
			pending_fail = apply_immediate_failure(mydict, failure, False)
			pending_fail = apply_immediate_failure(pseudo_dict, failure, True)
			if ("drop" in pending_fail):
				return
		elif (failure):
			output ("Replica", myreplica_id, " :Found failure", failure, "for get_run_state  at msg num ", get_run_state_msg_num)
			super().update_relevant_failure(failure, "get_run_state", -1, get_run_state_msg_num, pending_failures)
		mydict_sorted = OrderedDict(sorted(pseudo_dict.items()))
		send(('running_state', mydict_sorted, myreplica_id), to=olymp_config['config'])
		output("Replica", myreplica_id, " :sent running state \n", mydict_sorted, "to Olympus")
	


	def cache_result_shuttle(result_proof, client_id, client_req_id):
		output ("Replica", myreplica_id, " :Caching res proof for", client_id, client_req_id)
		key = (client_id, client_req_id)
		key = str(key)
		res_proof_cache[key] = {}
		res_proof_cache[key]['cached_result'] = copy.deepcopy(result_proof['result'])
		res_proof_cache[key]['cached_result_proof'] = copy.deepcopy(result_proof)


	def apply_immediate_failure(dest_dict, failure, repeat):
		output ("Replica",myreplica_id,  " :Applying immediate failure", failure)
		if "extra_op" in  failure:
			apply_operation(dest_dict, "put('a','a')")
		elif (repeat):
			return failure
		elif "sleep" in failure:
			p1=re.search("(?<=\().*(?=\))", failure)
			pair = p1.group()
			output ("Replica",myreplica_id,  " :sleeping for ", int(pair.strip()))
			sleep(int(pair.strip()))
		elif "crash"  in failure:
			logging.shutdown()
			os._exit(-1)
		elif "increment_slot" in failure:
			if (am_I_head):
				pending_slot_failure=True
		elif "drop" in failure:
			return "drop"
		return ""

	#handler for forward signed shuttles
	def receive(msg=('signed_fwd_shuttle_pkg', replica_id, signed_fwd_shuttle, client_id, client_req_id, signed_client_msg)):
		if (mode == 2):
			output ("Replica",myreplica_id, " :Client req in immutable mode, ignored")
			return
		output("\n\n")
		output ("Replica",myreplica_id,  " :Fwd_shuttle_pkg from replica", replica_id, "for client", client_id, "and req-id", client_req_id, "potential slot", next_slot_id)
		sender_public_key_hex = rep_pub_keys[replica_id]
		orig_fwd_shuttle = verify_signed_msg(sender_public_key_hex, signed_fwd_shuttle)
		client_public_key_hex = client_pub_keys[client_id]
		orig_client_msg = verify_signed_msg(client_public_key_hex, signed_client_msg)
		client_msg[client_id]['num_fwd_shutl'] += 1
		failure = super().check_for_failures(client_id, 'fwd_shutl', client_msg[client_id]['num_fwd_shutl'], rep_fail_triggers)
		if failure and any(x in failure for x in ["sleep", "crash", "extra_op", "drop", "increment_slot"]):
			pending_fail = apply_immediate_failure(mydict, failure, False)
			if (pending_fail == "drop"):
				return
		elif (failure):
			output ("Replica", myreplica_id, " :Found fwd_shutl failure", failure, "for client", client_id, "at msg num ", client_msg[client_id]['num_fwd_shutl'])
			super().update_relevant_failure(failure, "shuttle", client_id, client_msg[client_id]['num_fwd_shutl'], pending_failures)
		if (not orig_client_msg):
			output("Replica" ,myreplica_id, " :Could not verify signed client msg")
			return
		else:
			operation = orig_client_msg['operation']
		if not (orig_fwd_shuttle):
			output ("Replica",myreplica_id, " :fwd_pkg Could NOT verify the identity of msg from ", replica_id)
			return
		else:
			#orig_fwd_shuttle is of type Shuttle
			output("Replica",myreplica_id, " :verified sign of replica", replica_id)
			is_result =  orig_fwd_shuttle['is_result']
			order_proof = orig_fwd_shuttle['order_proof']
			result_proof = orig_fwd_shuttle['result_proof']
			#maybe use slot_id and replica_id too?
			(is_op_valid, next_slot_id) = super().validate_order_proof(order_proof, next_slot_id, operation)
			if not (is_op_valid):
				output("Replica",myreplica_id, " :Could NOT validate order proof")
				output ("Replica", myreplica_id, " :Complaining to olympus")
				#what to do now?
			else:
				output("Replica",myreplica_id, " :validated order proof")
				output("Replica",myreplica_id, " : Slot_id", order_proof['slot_id'], "operation", operation)
				key = (client_id, client_req_id)
				key = str(key)
				req_slot_map[key] = order_proof['slot_id']
				if (operation == "get(x)"):
					output ("something went very wrong")
					#fail_var=-1
				result=apply_operation(mydict, operation)
				if(am_I_tail):
					is_result=1
				else:
					is_result=0
				send_shuttle=super().create_new_shuttle(order_proof, result_proof, myreplica_id, is_result, result, my_priv_key, operation)
				if (am_I_tail):
					client_msg[client_id]['num_valid_res_shutl'] +=1
					cache_result_shuttle(result_proof, client_id, client_req_id)
				history.append(copy.deepcopy(order_proof))
				recent_client_req_map.appendleft(client_id)
				signed_res_stat_map[client_id]= (copy.deepcopy(result_proof['result_statements'][-1]), copy.deepcopy(order_proof['slot_id']), myreplica_id,)
				if (not am_I_tail and (len(pending_failures['fwd_shuttle']) != 0)):
					next_failure = pending_failures['fwd_shuttle'].pop(0)
					super().inject_failure(order_proof, result_proof, next_failure)
				if (am_I_tail and (len(pending_failures['res_shuttle']) != 0)):
					next_failure = pending_failures['res_shuttle'].pop(0)
					super().inject_failure(order_proof, result_proof, next_failure)
				signed_new_fwd_shuttle = generate_signed_msg(send_shuttle, my_priv_key)
				if (signed_new_fwd_shuttle):
					send_to_correct_replica(rep_config, myreplica_id, signed_new_fwd_shuttle, result, is_result, client_id, client_req_id, send_shuttle, signed_client_msg)
				else:
					output("Fwd: replica",myreplica_id, " :Error in fwd shuttle")


	def receive(msg=('signed_result_shuttle_pkg', replica_id, signed_res_shuttle, client_id, client_req_id)):
		output ("\n\n")
		if (mode == 2):
			output ("Replica",myreplica_id, " :Client req in immutable mode, ignored")
			return
		output ("Replica",myreplica_id,  " :Res_shuttle_pkg from replica", replica_id, "for client", client_id, "and req", client_req_id)
		sender_public_key_hex = rep_pub_keys[replica_id]
		client_msg[client_id]['num_res_shutl'] += 1
		failure = super().check_for_failures(client_id, 'res_shutl', client_msg[client_id]['num_res_shutl'], rep_fail_triggers)
		if failure and any(x in failure for x in ["sleep", "crash", "extra_op", "drop", "increment_slot"]):
			pending_fail = apply_immediate_failure(mydict, failure, False)
			if (pending_fail == "drop"):
				return
		elif (failure):
			output ("Replica", myreplica_id, " :Found failure", failure, "for client", client_id, "at msg_num ", client_msg[client_id]['num_res_shutl'])
			super().update_relevant_failure(failure, "result_shuttle", client_id, client_msg[client_id]['num_res_shutl'], pending_failures)
		orig_res_shuttle = verify_signed_msg(sender_public_key_hex, signed_res_shuttle)
		if not (orig_res_shuttle):
			output ("Replica",myreplica_id, " :Could NOT verify the identity of ", replica_id)
		else:
			output ("Replica",myreplica_id, " :Validated identity of ", replica_id)
			result_proof = orig_res_shuttle['result_proof']
			order_proof = orig_res_shuttle['order_proof']
			is_result = orig_res_shuttle['is_result']
			if not (super().validate_result_proof(result_proof)):
				output("Replica",myreplica_id, " :Could NOT validate result proof")
				output ("Replica", myreplica_id, " :Complaining to olympus")
				#what to do here
			else:
				client_msg[client_id]['num_valid_res_shutl'] +=1
				cache_result_shuttle(result_proof, client_id, client_req_id)
				output("Replica",myreplica_id, " :Validated result proof")
				if (not am_I_head and (len(pending_failures['res_shuttle']) != 0)):
					next_failure = pending_failures['res_shuttle'].pop(0)
					super().inject_failure(order_proof, result_proof, next_failure)
				send_shuttle = {'is_result':is_result, 'order_proof' : order_proof, 'result_proof' : result_proof}
				signed_new_res_shuttle = generate_signed_msg(send_shuttle, my_priv_key)
				result=result_proof['result']
				if(signed_new_res_shuttle):
					send_to_correct_replica(rep_config, myreplica_id, signed_new_res_shuttle, result, is_result, client_id, client_req_id, send_shuttle, "")
				else:
					output("Replica",myreplica_id, " :Error in res shuttle")


	#we go <order slot replica operation>
	def send_to_correct_replica(rep_config, myreplica_id, signed_send_shuttle, result, is_result, client_id, client_req_id, send_shuttle, signed_client_msg):
		if (is_result and not am_I_head and not am_I_tail):
			output("Replica", myreplica_id, " :sending bwd shuttle to", myreplica_id-1 ,"obj:" ,rep_config[myreplica_id-1], "\n")
			send(('signed_result_shuttle_pkg', myreplica_id, signed_send_shuttle, client_id, client_req_id), to=rep_config[myreplica_id-1])
			#cache and check
			#send_bwd
			pass
		elif (is_result and am_I_tail):
			output("Replica", myreplica_id, " :sending bwd shuttle to", myreplica_id-1 ,"obj:" ,rep_config[myreplica_id-1], "\n")
			send(('signed_result_shuttle_pkg', myreplica_id, signed_send_shuttle, client_id, client_req_id), to=rep_config[myreplica_id-1])
			key = (client_id, client_req_id)
			slot_key = str(key)
			if (len(pending_failures['only_client']) != 0):
				next_failure = pending_failures['only_client'].pop(0)
				super().inject_failure(send_shuttle['order_proof'], send_shuttle['result_proof'], next_failure)
			output("Replica", myreplica_id, " :sending result shuttle to client", client_id ,"obj:" ,client_config[client_id], "slot_id :", next_slot_id-1,"\n")
			send(('client_result_pkg', result, myreplica_id, signed_send_shuttle, client_req_id, longest_slot_len + req_slot_map[slot_key]), to=client_config[client_id])
			#sned to client & bwds
		elif(is_result and am_I_head):
			#do nothing
			pass
		if (not is_result and not am_I_tail):
			output("Replica", myreplica_id, " :sending fwd shuttle to ", myreplica_id+1, "obj", rep_config[myreplica_id+1], "\n")
			send(('signed_fwd_shuttle_pkg', myreplica_id, signed_send_shuttle, client_id, client_req_id, signed_client_msg), to=rep_config[myreplica_id+1])
			#send_fwd
			pass
		elif (not is_result and am_I_tail):
			pass
			#mark this as a result
			#send result shuttle bwd
			#send result proof to client along with result.


	def receive(msg=('rep_fwd_req',  operation, sender_replica_id, client_id, client_req_id, signed_client_msg)):
		output("\n\n")
		if (mode == 2):
			output ("Replica",myreplica_id, " :Client req in immutable mode, ignored")
			return
		output ("Replica",myreplica_id,  " :Forwarded request from replica", sender_replica_id, "for client", client_id, "and req_id", client_req_id)
		key = (client_id, client_req_id)
		key = str(key)
		client_msg[client_id]['num_fwd_req'] += 1
		failure = super().check_for_failures(client_id, 'fwd_req', client_msg[client_id]['num_fwd_req'], rep_fail_triggers)
		if failure and any(x in failure for x in ["sleep", "crash", "extra_op", "drop", "increment_slot"]):
			pending_fail = apply_immediate_failure(mydict, failure, False)
			if (pending_fail == "drop"):
				return
		elif (failure):
			output ("Replica", myreplica_id, " :Found failure", failure ,"for client", client_id, "at msg_num ", client_msg[client_id]['num_fwd_req'])
			super().update_relevant_failure(failure, "forwarded_request", client_id, client_msg[client_id]['num_fwd_req'], pending_failures)
		if (curr_handling_req == (key)):
			output("Replica", myreplica_id, " :Forwarded req from replica" ,sender_replica_id, "already handling", key)
			return
		else:
			output ("Replica", myreplica_id, " :Forwarded req from replica" ,sender_replica_id, "Will handle ", key)
			curr_handling_req = key

		if (key in res_proof_cache):
			output ("Replica", myreplica_id, " :Found cached result for", client_id, "with req id", client_req_id)
			result_proof = res_proof_cache[key]['cached_result_proof']
			result = res_proof_cache[key]['cached_result']
			order_proof = {}
			if (len(pending_failures['res_shuttle']) != 0):
				next_failure = pending_failures['res_shuttle'].pop(0)
				super().inject_failure(order_proof, result_proof, next_failure)
			send_shuttle = {'result_proof': result_proof}
			signed_send_shuttle = generate_signed_msg(send_shuttle, my_priv_key)
			send(('client_result_pkg', result, myreplica_id, signed_send_shuttle, client_req_id, longest_slot_len + req_slot_map[key]), to=client_config[client_id])
		else:
			handle_retransmitted_req(key, operation, sender_replica_id, client_id, client_req_id, signed_client_msg)


	def handle_retransmitted_req(key, operation, sender_replica_id, client_id, client_req_id, signed_client_msg):
		#head has ordered this operation
		TIMEOUT = mytimeout
		if (curr_handling_req == (key)):
			if (not (sender_replica_id == 0)):
				output("Replica", myreplica_id, " :Forwarded req from replica" ,sender_replica_id, "already handling", key)
			return
		else:
			if (not (sender_replica_id == 0)):
				output ("Replica", myreplica_id, " :Forwarded req from replica" ,sender_replica_id, "Will handle ", key)
			curr_handling_req = key
		if key in req_slot_map:
			exp_val = client_msg[client_id]['num_valid_res_shutl'] + 1
			#wait for timer to expire or a res_shuttle to arrive
			output ("Replica", myreplica_id, "  :Have seen this req and Starting timer waiting for (", client_req_id, client_id,") to arrive")
			if (await(client_msg[client_id]['num_valid_res_shutl'] == exp_val)):
				result_proof = res_proof_cache[key]['cached_result_proof']
				result = res_proof_cache[key]['cached_result']
				order_proof = {}
				if (len(pending_failures['res_shuttle']) != 0):
					next_failure = pending_failures['res_shuttle'].pop(0)
					super().inject_failure(order_proof, result_proof, next_failure)
				send_shuttle = {'result_proof': result_proof}
				signed_send_shuttle = generate_signed_msg(send_shuttle, my_priv_key)
				output ("Replica", myreplica_id, "  :Res proof arrived and sending to client ", client_id)
				send(('client_result_pkg', result, myreplica_id, signed_send_shuttle, 																client_req_id, longest_slot_len + req_slot_map[key]), to=client_config[client_id])
			elif timeout(TIMEOUT):
				output ("Replica", myreplica_id, "  :Timed out and Complaining to Olympus for req-id", client_req_id, "from client" , client_id)
				send(('reconfig_req', myreplica_id, True), to=olymp_config['config'])
		else:
			#start from scratch
			output ("Replica", myreplica_id, "  :Have not seen this retransmitted request <", client_req_id, client_id,  "> before , will start from scratch")

			if (pending_slot_failure and am_I_head):
				output("Replica",myreplica_id, " :slot failure injected")
				next_slot_id += 1
				pending_slot_failure=False
			is_result=0
			order_proof={}
			key = (client_id, client_req_id)
			slot_key = str(key)
			#have an if check here?
			order_proof['slot_id'] = next_slot_id
			req_slot_map[slot_key] = next_slot_id
			next_slot_id += 1
			order_proof['op'] = operation
			result_proof={}
			result=apply_operation(mydict, operation)
			order_proof['order_statements']=[]
			result_proof['result_statements'] =[]
			#result_proof['slot_id'] = []

			send_shuttle=super().create_new_shuttle(order_proof, result_proof, myreplica_id, is_result, result, my_priv_key, operation)
			history.append(copy.deepcopy(order_proof))
			recent_client_req_map.appendleft(client_id)
			signed_res_stat_map[client_id]= (copy.deepcopy(result_proof['result_statements'][-1]), copy.deepcopy(order_proof['slot_id']), myreplica_id)

			if (len(pending_failures['fwd_shuttle']) != 0):
				next_failure = pending_failures['fwd_shuttle'].pop(0)
				super().inject_failure(order_proof, result_proof, next_failure)
			signed_new_fwd_shuttle = generate_signed_msg(send_shuttle, my_priv_key)
			send_to_correct_replica(rep_config, myreplica_id, signed_new_fwd_shuttle,  
							result, is_result, client_id, client_req_id, send_shuttle, signed_client_msg)
			exp_val = client_msg[client_id]['num_valid_res_shutl'] + 1
			#wait for timer to expire or a res_shuttle to arrive
			output ("Replica", myreplica_id, "  :Scratch start, Starting timer waiting for (", client_req_id, client_id,") to arrive")
			if (await(client_msg[client_id]['num_valid_res_shutl'] == exp_val)):
				result_proof = res_proof_cache[key]['cached_result_proof']
				result = res_proof_cache[key]['cached_result']
				order_proof = {}
				if (len(pending_failures['res_shuttle']) != 0):
					next_failure = pending_failures['res_shuttle'].pop(0)
					super().inject_failure(order_proof, result_proof, next_failure)
				send_shuttle = {'result_proof': result_proof}
				signed_send_shuttle = generate_signed_msg(send_shuttle, my_priv_key)
				output ("Replica", myreplica_id, "  :Res proof arrived and sending to client ", client_id)
				send(('client_result_pkg', result, myreplica_id, signed_send_shuttle, 																client_req_id, longest_slot_len + req_slot_map[slot_key]), to=client_config[client_id])
			elif timeout(TIMEOUT):
				output ("Replica", myreplica_id, "  :Timed out and Complaining to Olympus for req-id", client_req_id, "from client" , client_id)
				send(('reconfig_req', myreplica_id, True), to=olymp_config['config'])


	#signed_client_msg: signed<op, is_retransmit>
	def receive(msg=('client_op_req',  signed_client_msg, client_id, client_req_id)):
		output("\n\n")
		if (mode == 2):
			output ("Replica",myreplica_id, " :Client req in immutable mode, ignored")
			return
			
		TIMEOUT = mytimeout
		output ("Replica",myreplica_id,  " :Client_op request from client", client_id, "with req_id", client_req_id, "potential slot_id", next_slot_id)
		client_msg[client_id]['num_client_req'] += 1
		failure = super().check_for_failures(client_id, 'client_req', client_msg[client_id]['num_client_req'], rep_fail_triggers)
		if failure and any(x in failure for x in ["sleep", "crash", "extra_op", "drop", "increment_slot"]):
			pending_fail = apply_immediate_failure(mydict, failure, False)
			if (pending_fail == "drop"):
				return
		elif (failure):
			output ("Replica", myreplica_id, " :Found failure", failure ,"for client", client_id, "at msg_num ", client_msg[client_id]['num_client_req'])
			super().update_relevant_failure(failure, 'client_request', client_id, client_msg[client_id]['num_client_req'], pending_failures)
		sender_public_key_hex = client_pub_keys[client_id] #0 is the client
		orig_client_msg = verify_signed_msg(sender_public_key_hex, signed_client_msg)
		if not (orig_client_msg):
			output ("Replica",myreplica_id, " :Could NOT verify the identity of msg from client")
			return
		else:
			output("Replica",myreplica_id, " :Verified sign of client", client_id)
			is_retransmit =  orig_client_msg['is_retransmit']
			operation = orig_client_msg['operation']
			if (is_retransmit):
				output("Replica",myreplica_id, " :This is a retransmitted request client-id", client_id, "with req", client_req_id)
				#do I have this result cached?
				key = (client_id, client_req_id)
				key = str(key)
				if (key in res_proof_cache):
					output ("Replica", myreplica_id, " :Found cached result for", client_id, "with req id", client_req_id)
					result_proof = res_proof_cache[key]['cached_result_proof']
					result = res_proof_cache[key]['cached_result']
					order_proof = {}
					if (len(pending_failures['res_shuttle']) != 0):
						next_failure = pending_failures['res_shuttle'].pop(0)
						super().inject_failure(order_proof, result_proof, next_failure)
					send_shuttle = {'result_proof': result_proof}
					signed_send_shuttle = generate_signed_msg(send_shuttle, my_priv_key)
					send(('client_result_pkg', result, myreplica_id, signed_send_shuttle, client_req_id, 
									longest_slot_len + req_slot_map[key]), to=client_config[client_id])
				elif (not am_I_head):
					output ("Replica", myreplica_id, " :Cache lookup for req",client_req_id, "from", client_id,"failed, Sending fwd req to head")
					send(('rep_fwd_req', operation, myreplica_id, client_id, client_req_id, signed_client_msg), to=rep_config[0])
					exp_val = client_msg[client_id]['num_valid_res_shutl'] + 1
					#wait for timer to expire or a res_shuttle to arrive, is the check correct
					#would it be good to check for specific req id
					output ("Replica", myreplica_id, "  :Starting timer waiting for (", client_req_id, client_id,") to arrive")
					if (await(client_msg[client_id]['num_valid_res_shutl'] == exp_val)):
						result_proof = res_proof_cache[key]['cached_result_proof']
						result = res_proof_cache[key]['cached_result']
						order_proof = {}
						if (len(pending_failures['res_shuttle']) != 0):
							next_failure = pending_failures['res_shuttle'].pop(0)
							super().inject_failure(order_proof, result_proof, next_failure)
						send_shuttle = {'result_proof': result_proof}
						signed_send_shuttle = generate_signed_msg(send_shuttle, my_priv_key)
						output ("Replica", myreplica_id, "  :Res proof arrived and sending to client ", client_id)
						if (not am_I_tail):#tail must have sent anyway
							send(('client_result_pkg', result, myreplica_id, signed_send_shuttle, 															client_req_id, longest_slot_len + req_slot_map[key]), to=client_config[client_id])
					elif timeout(TIMEOUT):
						output ("Replica", myreplica_id, "  :Timed out and Complaining to Olympus for req-id", client_req_id, "from client" , client_id)
						send(('reconfig_req', myreplica_id, True), to=olymp_config['config'])
				elif (am_I_head):
					#head has ordered this operation
					output ("Replica", myreplica_id, "  or HEAD could not find (", client_id, client_req_id,") in cache")
					handle_retransmitted_req(key, operation, myreplica_id, client_id, client_req_id, signed_client_msg)

			else:
				output("Replica",myreplica_id, " :Client_req got operation", operation)
				if (pending_slot_failure and am_I_head):
					output("Replica",myreplica_id, " :slot failure injected")
					next_slot_id += 1
					pending_slot_failure=False
				is_result=0
				order_proof={}
				key = (client_id, client_req_id)
				slot_key = str(key)
				#have an if check here?
				order_proof['slot_id'] = next_slot_id
				req_slot_map[slot_key] = next_slot_id
				next_slot_id += 1
				order_proof['op'] = operation
				result_proof={}
				result=apply_operation(mydict, operation)
				order_proof['order_statements']=[]
				result_proof['result_statements'] =[]
				#result_proof['slot_id'] = []

				send_shuttle=super().create_new_shuttle(order_proof, result_proof, myreplica_id, is_result, result, my_priv_key, operation)
				history.append(copy.deepcopy(order_proof))
				recent_client_req_map.appendleft(client_id)
				signed_res_stat_map[client_id]= (copy.deepcopy(result_proof['result_statements'][-1]), copy.deepcopy(order_proof['slot_id']), myreplica_id)
				'''
				if (am_I_head):
					if (dummy_msg_num == 4):
						return
					else:
						dummy_msg_num +=1
				'''
	
				if (len(pending_failures['fwd_shuttle']) != 0):
					next_failure = pending_failures['fwd_shuttle'].pop(0)
					super().inject_failure(order_proof, result_proof, next_failure)
				signed_new_fwd_shuttle = generate_signed_msg(send_shuttle, my_priv_key)
				send_to_correct_replica(rep_config, myreplica_id, signed_new_fwd_shuttle,  result, is_result, client_id, client_req_id, send_shuttle, signed_client_msg)


	def apply_operation(dest_dict, operation):
		operation = operation.strip()
		output ("applying op ", operation)
		p1=re.search("(?<=\().*(?=\))", operation)
		if (p1):
			pair = p1.group()
			pair = pair.split(",")
			if not operation.startswith("get"):
				pair[1] = pair[1].strip("'")
				val = pair[1]
				val = int(val.strip()) if str.isdecimal(val) else val.strip()
			pair[0] = pair[0].strip("'")
			key = pair[0]
			key = int(key.strip()) if str.isdecimal(key) else key.strip()
		if (operation.startswith("get")):
			output ("Get operation")
			if key in dest_dict:
				result = dest_dict[key]
			else:
				result=""
		elif (operation.startswith("put")):
			output ("Put operation")
			dest_dict[key] = val
			result= "OK"
		elif (operation.startswith("slice")):
			output ("Slice operation", key, val)
			val=val.split(":")
			val[0]= val[0].strip("'")
			val[1] = val[1].strip("'")
			si = int(val[0])
			fi = int(val[1])
			if key in dest_dict:
				if ((si in range(0,len(dest_dict[key]) +1)) and (fi in range(len(dest_dict[key])+1))):
					dest_dict[key] = dest_dict[key][si:fi]
					result = "OK"
				else:
					result = 'fail'
			else:
				result = 'fail'
		elif (operation.startswith("append")):
			output ("Append Operation", key, val)
			if key in dest_dict:
				dest_dict[key]+=(val)
				result="OK"
			else:
				result="fail"
		else:
			output ("Invalid Operation, returning fail")
			return "fail"
		output ("Result:", result, "")
		return result

	def run():
		config_file = sys.argv[1]
		config(clock='Lamport')
		output ("Config file", config_file)
		output("\n\n\n")
		output("Replica", myreplica_id, "started:  with config num", curr_config_num,"am_I_head" ,am_I_head, "am_I_tail", am_I_tail)
		output("Replica", myreplica_id, "run state", mydict)
		
########
		#return
########
		config = parse_file(config_file)
		rep_fail_triggers = get_rep_fail_triggers(config, myreplica_id, curr_config_num)

		failure = super().check_for_failures(-1, 'new_config', curr_config_num, rep_fail_triggers)
		if failure and any(x in failure for x in ["sleep", "crash", "extra_op", "drop", "increment_slot"]):
			pending_fail = apply_immediate_failure(mydict, failure, False)
			if (pending_fail == "drop"):
				output ("Replica", myreplica_id, " :Found failure", pending_fail, "!!!!!!!!")
				return
		elif (failure):
			output ("Replica", myreplica_id, " :Found failure", failure, "for new_config at msg num ", curr_config_num)
			super().update_relevant_failure(failure, "new_config", -1, curr_config_num, pending_failures)

		num_clients = get_num_clients(config)
		if (am_I_head):
			mytimeout = get_head_timeout(config)
			mytimeout = mytimeout/1000
			output ("Head: Got timeout\n", mytimeout, "\n",)
		else:
			mytimeout = get_non_head_timeout(config)
			mytimeout = mytimeout/1000
			output ("Non head: Got timeout", mytimeout, "\n")
			
		for i in range(num_clients):
			client_msg[i] ={}
			client_msg[i]['num_fwd_shutl']=-1
			client_msg[i]['num_res_shutl']=-1
			client_msg[i]['num_client_req']=-1
			client_msg[i]['num_fwd_req']=-1
			client_msg[i]['num_valid_res_shutl']=-1

		output ("Replica", myreplica_id, "Fail_triggers for config num",curr_config_num, ":", rep_fail_triggers, "num_clients", num_clients, "\n\n\n")
		if (am_I_head):
			while(True):
				
				--wait
		else:
			while(True):
				--wait
