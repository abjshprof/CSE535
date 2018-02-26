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

#res_shuttle: dict with res_shuttle_client = signed(result, result_proof)
class Central_Client(process):
	def setup(num_clients, client_config):
		self.client_dicts={}
		self.num_received_dicts=0
		self.cen_client_dict={}

	#handler for forward signed shuttles
	def receive(msg=('client_verify_res', rep_res, exp_res, client_id)):
		output ("Got msg from client:", client_id)
		client_dicts[client_id] = {}
		client_dicts[client_id]['rep_res'] = rep_res
		client_dicts[client_id]['exp_res'] = exp_res
		num_received_dicts += 1

	def apply_operation(operation):
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
			#output ("Get operation")
			if key in cen_client_dict:
				result = cen_client_dict[key]
			else:
				result=""
		elif (operation.startswith("put")):
			#output ("Put operation")
			cen_client_dict[key] = val
			result= "OK"
		elif (operation.startswith("slice")):
			#output ("Slice operation")
			val=val.split(":")
			val[0]= val[0].strip("'")
			val[1] = val[1].strip("'")
			si = int(val[0])
			fi = int(val[1])
			if key in cen_client_dict:
				if ((si in range(0,len(cen_client_dict[key]) +1)) and (fi in range(len(cen_client_dict[key])+1))):
					cen_client_dict[key] = cen_client_dict[key][si:fi]
					result = "OK"
				else:
					result = 'fail'
			else:
				result = 'fail'
		elif (operation.startswith("append")):
			#output ("Append Operation")
			if key in cen_client_dict:
				cen_client_dict[key]+=(val)
				result="OK"
			else:
				result="fail"
		else:
			#output ("Invalid Operation, returning fail")
			return "fail"
		#output ("Result:", result, "")
		return result

	def merge_dicts(dict1, dict2):
		dicts= [dict1, dict2]
		merged_dict = {}
		for dict_ in dicts:
			for key, item in dict_.items():
				if key in merged_dict:
					temp = merged_dict[key]
					if type(temp) != list:
						temp = [temp]
					merged_dict[key] = temp + [item]
				else:
					merged_dict[key] = item
		return merged_dict





	def run():
		config(clock='Lamport')
######
		#return
#########
		await (num_received_dicts == num_clients)
		central_rep_res = {}
		central_exp_res = {}
		central_rep_res_list = []
		central_exp_res_list = []
		for i in range(num_clients):
			#print ("type", type(client_dicts[i]['rep_res']) , "and contents", client_dicts[i]['rep_res'])
			central_rep_res = merge_dicts(central_rep_res, client_dicts[i]['rep_res'])
			for key, value in client_dicts[i]['exp_res'].items():
				if (value['slot'] == -1):
					output("\n\n")
					output("Failure, req-id ", key, "from client", i, "did not succeed")
					return
				central_exp_res.update({value['slot']: value['op']})

		#for key in central_rep_res.items():
		#	if len(central_rep_res.items[key]) == 1:
		#		central_rep_res.items[key] = central_rep_res.items[key][0]

		print ("")
		for key, value in central_rep_res.items():
			if len(central_rep_res[key]) == 1:
				value = central_rep_res[key][0]
			central_rep_res_list.append(value)

		for key, value in central_exp_res.items():
			central_exp_res_list.append(apply_operation(value))

		if (central_rep_res_list == central_exp_res_list):
			output("\n\n\n")
			output ("results are correct")
			output ("central_rep_res_list: ", central_rep_res_list)
			output ("central_exp_res_list: ", central_exp_res_list)
			output ("all is well")
		else:
			output ("Expected", central_exp_res_list)
			output ("But obtained", central_rep_res_list)
			output ("Failure")
