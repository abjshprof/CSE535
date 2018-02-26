import da
import sys
import os
import logging
from validate_msg import validate_integrity
from create_hash import create_hash_and_encode_msg
from sign_msg import generate_signed_msg
from sign_msg import gen_invalid_sign_msg
from verify_sign import verify_signed_msg
from read_config import parse_file
from read_config import get_rep_fail_triggers
from read_config import get_num_clients
from read_config import get_non_head_timeout
from read_config import get_head_timeout

class Helpers(process):

	def setup(rep_setup):
		self.rep_config, self.myreplica_id, self.rep_pub_keys, self.client_config, self.client_pub_keys, self.my_priv_key, self.am_I_head, self.am_I_tail, self.olymp_config, self.new_values = rep_setup
		self.curr_config_num = new_values['curr_config_num']
		self.mydict = new_values['mydict']
		self.longest_slot_len = new_values['longest_slot_len']
		output("Replica:   ",myreplica_id ,"In inherited setup")
		pass

	def run():
		pass
	def create_new_shuttle(order_proof, result_proof, myreplica_id, is_result, result, my_priv_key, operation):
		slot_id = order_proof['slot_id']
		order_stat = {'order_tag':"order", 'slot_id':slot_id, 'replica_id' : myreplica_id, 'op': operation}
		signed_order_stat = generate_signed_msg(order_stat, my_priv_key)
		result_msg_hash = create_hash_and_encode_msg(result)
		result_stat = {'result_tag':"result", 'slot_id': slot_id, 'op':operation, 'result':result, 'digest':result_msg_hash.digest}
		signed_result_stat = generate_signed_msg(result_stat, my_priv_key)
		order_proof['order_statements'].append(signed_order_stat)
		result_proof['result_statements'].append(signed_result_stat)
		result_proof['result'] = result
		#>>>>head has to set other fields like slot_id and op
		#>>>>perhaps assume they are already set
		order_proof['replica_id'] = myreplica_id
		result_proof['replica_id'] = myreplica_id
		#now create the shuttle
		send_shuttle = {'is_result':is_result, 'order_proof' : order_proof, 'result_proof' : result_proof}
		return send_shuttle


	def validate_order_proof(order_proof, next_slot_id, operation):
		output("Replica" ,myreplica_id, " :Trying to validate order proof")
		order_statements = order_proof['order_statements']
		if (len(order_statements) != (myreplica_id)):
			output ("Replica", myreplica_id, " :Length of order proof not correct")
			return (None,next_slot_id)
		expected_slot = next_slot_id
		slot_id = order_proof['slot_id']
		if (slot_id != expected_slot):
			output ("Replica", myreplica_id, " :OP validation did not expect this slot_id; exp:",expected_slot , "got ", slot_id)
			return (None, next_slot_id)
		for index, ostat in enumerate(order_statements):
			#output (">>",index, ostat)
			sender_public_key_hex = rep_pub_keys[index]
			orig_stat=verify_signed_msg(sender_public_key_hex, ostat)
			if(orig_stat):
				#output ("Replica", myreplica_id, " :Verified signature of replica ", index)
				#output("validated order proof, type orig_stat", type(orig_stat), "sid", orig_stat['slot_id'], "op",orig_stat['op'])
				if ((slot_id == orig_stat['slot_id']) and (operation == orig_stat['op'])):
					continue
				else:
					output ("Replica: ", myreplica_id, "Order Proof validation mismatch for sender ", index)
					return (None,next_slot_id)
			else:
				output ("Replica: ", myreplica_id, "Order Proof validation Could not verify id of sender ", index)
				return (None,next_slot_id)
		next_slot_id += 1
		return (1,next_slot_id)


	def validate_result_proof(result_proof):
		output("Replica",myreplica_id, " :Trying to validate result proof")
		result_statements = result_proof['result_statements']
		result = result_proof['result']
		result_hash = create_hash_and_encode_msg(result).digest
		op_list= []
		for index, rstat in enumerate(result_statements):
			#output (">>",index)
			sender_public_key_hex = rep_pub_keys[index]
			orig_stat=verify_signed_msg(sender_public_key_hex, rstat)
			if(orig_stat):
				#output ("Replica", myreplica_id, " :Verified signature of replica ", index)
				op_list.append(orig_stat['op'])
				if ((result == orig_stat['result']) and (result_hash == orig_stat['digest'])):
					continue
				else:
					output ("Replica",myreplica_id, " :result proof error, validation mismatch for sender ", index)
					return None
			else:
				output ("Replica",myreplica_id, " :result proof error, vCould not verify id of sender ", index)
				return None
		if (len(set(op_list)) != 1):
			output ("Replica",myreplica_id, " :Invald operation in result proof")
			return None
		else:
			return 1

	# if it is an immediate failure, apply it else store for future
	def check_for_failures(client_id, fail_str, msg_num, rep_fail_triggers):
		output ("Replica",myreplica_id, " :checking for failures for client: ", client_id, "msg_num", msg_num, "for trigger", fail_str)
		if fail_str in rep_fail_triggers:
			this_trig_fails = rep_fail_triggers[fail_str]
			if client_id in this_trig_fails['myclients']:
				#output ("found fail client id", client_id)
				client_msg_op_map = this_trig_fails['client_msg_op_map']
				if msg_num in client_msg_op_map[client_id]:
					fail_op = client_msg_op_map[client_id][msg_num]
					output ("Replica",myreplica_id, " :Found fail_op" ,fail_op,"for client_id", client_id, "and msg", msg_num )
					return fail_op
		return ""


	#this is unsafe, inject *after* creating the proofs
	def inject_failure(order_proof, result_proof, next_failure):
		output ("Checking pending faiures for replica", myreplica_id)
		nreplicas = len(rep_config)
		trigger = next_failure[1]
		if "change_result" in next_failure[0]:
			output ("Replica", myreplica_id, " : { Trigger  :", trigger, " : failure <change_result> } injected in result_shuttle_pkg")
			result_msg_hash = create_hash_and_encode_msg("OK")
			sender_public_key_hex = rep_pub_keys[myreplica_id]
			myindex = myreplica_id
			if (len(result_proof['result_statements']) < nreplicas):
				output ("Replica", myreplica_id, " : Changing result and btw, someone already dropped Head's result statement")
				myindex = myreplica_id -1
			orig_rstat=verify_signed_msg(sender_public_key_hex, result_proof['result_statements'][myindex])
			if (orig_rstat):
				orig_rstat['digest'] = result_msg_hash.digest
				signed_result_stat = generate_signed_msg(orig_rstat, my_priv_key)
				result_proof['result_statements'][myindex] = signed_result_stat
			else:
				output ("FAILED TO INJECT FAILURE : COuld not verify sign of ", myindex)
		elif "drop_result_stmt" in next_failure[0]:
			#is nullifying better than omitting
			output ("Replica", myreplica_id, " : { Trigger", trigger," : failure <drop_result_stmt> } injected in result_shuttle_pkg")
			if (len(result_proof['result_statements']) < nreplicas):
				output ("Replica", myreplica_id, " : Someone already dropped Head's result statement, ignoring")
			else:
				output ("Replica", myreplica_id, " : Dropping head res statement")
				del(result_proof['result_statements'][0])
		elif "change_operation" in next_failure[0]:
			output ("Replica", myreplica_id, " : { Trigger", trigger," : failure <change_operation> } injected in fwd_shuttle_pkg")
			sender_public_key_hex = rep_pub_keys[myreplica_id]
			orig_ostat = verify_signed_msg(sender_public_key_hex, order_proof['order_statements'][myreplica_id])
			orig_rstat = verify_signed_msg(sender_public_key_hex, result_proof['result_statements'][myreplica_id])
			if (orig_ostat and orig_rstat):
				orig_ostat['op'] = "get(x)"
				orig_rstat['op'] = "get(x)"
				signed_order_stat = generate_signed_msg(orig_ostat, my_priv_key)
				signed_result_stat = generate_signed_msg(orig_rstat, my_priv_key)
				order_proof['order_statements'][myreplica_id] = signed_order_stat
				result_proof['result_statements'][myreplica_id] =  signed_result_stat
			else:
				output ("Replica", myreplica_id, " : Invalid sign on order or rstat; order stat", orig_ostat,"result_stat" ,orig_rstat)	
		elif "invalid_order_sig" in next_failure[0]:
			orig_ostat = order_proof['order_statements'][myreplica_id]
			invalid_ostat = gen_invalid_sign_msg(orig_ostat)
			order_proof['order_statements'][myreplica_id] = invalid_ostat
			output ("Replica", myreplica_id, " : { Trigger", trigger," : failure <invalid_order_sig> } injected in fwd_shuttle_pkg")
		elif "invalid_result_sig" in next_failure[0]:
			myindex = myreplica_id
			if ((len(result_proof['result_statements']) < nreplicas) and am_I_tail):
				output ("Replica", myreplica_id, " : Invalidating result stat and btw, someone already dropped Head's result statement")
				myindex = myreplica_id -1
			orig_rstat =  result_proof['result_statements'][myindex]
			invalid_rstat = gen_invalid_sign_msg(orig_rstat)
			result_proof['result_statements'][myindex] = invalid_rstat
			output ("Replica", myreplica_id, " : { Trigger", trigger," : failure <invalid_result_sig> } injected in res_shuttle_pkg")


	def update_relevant_failure(failure, trigger_type, client_id, msg_num, pending_failures):
		trigger = trigger_type + "(" + str(client_id) + "," + str(msg_num) + ")"
		if "change_operation" in failure:
			trig_fail_pair = (failure, trigger)
			pending_failures['fwd_shuttle'].append(trig_fail_pair)
			output ("Replica", myreplica_id, " :Updated fwd failure:   {", trig_fail_pair[1], " : ", trig_fail_pair[0], "}")
		elif (("change_result" in failure) or ("drop_result_stmt" in failure)):
			trig_fail_pair = (failure, trigger)
			pending_failures['res_shuttle'].append(trig_fail_pair)
			output ("Replica", myreplica_id, " :Updated res failure:   {", trig_fail_pair[1], " : ", trig_fail_pair[0], "}")
		elif ("invalid_result_sig" in failure):
			trig_fail_pair = (failure, trigger)
			if (not am_I_tail):
				pending_failures['fwd_shuttle'].append(trig_fail_pair)
			else:
				pending_failures['only_client'].append(trig_fail_pair)
			output ("Replica", myreplica_id, " :Updated fwd failure:   {", trig_fail_pair[1], " : ", trig_fail_pair[0], "}")
		elif ("invalid_order_sig" in failure):
			trig_fail_pair = (failure, trigger)
			pending_failures['fwd_shuttle'].append(trig_fail_pair)
			output ("Replica", myreplica_id, " :Updated fwd failure:   {", trig_fail_pair[1], " : ", trig_fail_pair[0], "}")
		elif ("truncate_history" in failure):
			trig_fail_pair = (failure, trigger)
			pending_failures['wedge_msg'].append(trig_fail_pair)
			output ("Replica", myreplica_id, " :Updated wedged failure:   {", trig_fail_pair[1], " : ", trig_fail_pair[0], "}")
