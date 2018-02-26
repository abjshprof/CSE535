import re
def parse_file(filename):
	config={}
	with open(filename,'r') as f:
		for line in f:
			if line[0] != '#':
				(key,sep,val) = line.partition('=')
		  		# if the line does not contain '=', it is invalid and hence ignored
				if len(sep) != 0:
					val = val.strip()
					if (key.strip() == 't'):
						num_replicas= 2*int(val.strip()) + 1
						key = "num_replicas"
						print ("num_replicas", num_replicas)
					elif (key.strip() == "test_case_name"):
						test_case_name = val.strip()
						print ("test case name", test_case_name)
					elif (key.strip() == 'num_client'):
						num_clients = int(val.strip())
						print ("num_clients", num_clients)
					elif (key.strip() == 'client_timeout'):
						client_timeout = int(val.strip())
						print ("client_timeout", client_timeout)
					elif (key.strip() == 'head_timeout'):
						head_timeout = int(val.strip())
						print ("head_timeout", head_timeout)
					elif (key.strip() == 'nonhead_timeout'):
						nonhead_timeout = int(val.strip())
						print ("nonhead_timeout", nonhead_timeout)
					config[key.strip()] = int(val.strip()) if str.isdecimal(val) else val.strip()
	return config
	#print(config)
#replica_fail_triggers = []


	
#trig_fail = {client, failure}

def get_msg_and_client_num(other_str, msg_num, client_num):
	print ("other_str", other_str)
	p1=re.search("(?<=\().*(?=\))", other_str)
	if (p1):
		pair = p1.group()
		pair = pair.split(",")
		if (len(pair) == 1):
			return (int(pair[0]), -1)
		pair[1] = pair[1].strip("'")
		msg_num = pair[1]
		msg_num = int(msg_num.strip()) if str.isdecimal(msg_num) else msg_num.strip()
		pair[0] = pair[0].strip("'")
		client_num = pair[0]
		client_num =  int(client_num.strip()) if str.isdecimal(client_num) else client_num.strip()
	return (int(msg_num), int(client_num))
	#print ("msg_num", msg_num, "and client_num ", client_num)

def initialize_dict(relevant_dict):
	for i in ('client_req', 'fwd_req', 'fwd_shutl', 'res_shutl', 'get_run_state', 'catch_up', 'new_config', 'wedge_req'):
		relevant_dict[i] = {}
		tmp = relevant_dict[i]
		tmp['myclients'] = set()
		tmp['client_msg_op_map'] = {}

#op is the actual failure
#field - trigger
def update_dict(relevant_dict, field, msg_num, client_num, op):
	tmp = relevant_dict[field]
	tmp['myclients'].add(int(client_num))
	client_msg_op_map=tmp['client_msg_op_map']
	if (not client_num in client_msg_op_map):
		client_msg_op_map[client_num] = {}
	client_msg_op_map[client_num].update({msg_num: op})

#field = trigger alias
#fail_str - trigger, fail pair as it appears in config, e.g. client_request(0,1),  change_result()

def create_entry(fail_str, field, relevant_dict):
	print ("got fail_str", fail_str)
	groups = fail_str.split(',')
	#print ("groups", groups)
	if (len(groups) > 2):
		new_list = ','.join(groups[:2]), ','.join(groups[2:])
	else:
		new_list=groups
	print ("new_list", new_list)
	op = new_list[1].strip()
	other_str = new_list[0].strip()
	msg_num=-1
	client_num=-1
	msg_client_pair = get_msg_and_client_num(other_str, msg_num, client_num)
	update_dict(relevant_dict, field, msg_client_pair[0], msg_client_pair[1], op)
	#print ("msg_num", msg_client_pair[0], "and client_num ", msg_client_pair[1], "and op", op)
	

def construct_my_info(myfailures):
	relevant_dict={}
	initialize_dict(relevant_dict)
	#print ("\n>>>>",relevant_dict)
	for i in myfailures:
		i.strip()
		if (i.startswith("shuttle")):
			create_entry(i, 'fwd_shutl', relevant_dict)
		elif (i.startswith("result_shuttle")):
			create_entry(i, 'res_shutl', relevant_dict)
		elif (i.startswith("client_request")):
			create_entry(i, 'client_req', relevant_dict)
		elif (i.startswith("forwarded_request")):
			create_entry(i, 'fwd_req', relevant_dict)
		elif (i.startswith("get_running_state")):
			create_entry(i, 'get_run_state', relevant_dict)
		elif (i.startswith("catch_up")):
			create_entry(i, 'catch_up', relevant_dict)
		elif (i.startswith("new_configuration")):
			create_entry(i, 'new_config', relevant_dict)
		elif (i.startswith("wedge_request")):
			create_entry(i, 'wedge_req', relevant_dict)

	return relevant_dict

def get_rep_fail_triggers(config, myreplica_id, config_num):
	rep = myreplica_id
	key = "failures[" + str(config_num) + "," + str(myreplica_id) + "]"
	if (key in config):
		#print ("\n rep:", rep, "relevant to this replica\n", config[key])
		rep_failures = config[key]
		rep_failures=rep_failures.split(";")
		rep_failures = [x.strip(' ') for x in rep_failures]
		#print ("rep", rep, ">>rep_failures\n", rep_failures)
		rep_failures.sort()
		myinfo = construct_my_info(rep_failures)
		#print ("myinfo", myinfo)
		return myinfo
	return {}

def get_client_load(config, myclient_id):
	client_load=[]
	cl = myclient_id
	key = "workload[" + str(myclient_id) + "]"
	if (key in config):
		#print ("\n relevant to this client\n", config[key])
		myclient_load = config[key]
		myclient_load = myclient_load.split(";")
		myclient_load = [x.strip(' ') for x in myclient_load]
		#print ("client", cl, ">> client_load", myclient_load)
		return myclient_load

def get_client_timeout(config):
	return config['client_timeout']

def get_head_timeout(config):
	return config['head_timeout']

def get_non_head_timeout(config):
	return config['nonhead_timeout']

def get_num_replicas(config):
	num_replicas = config['num_replicas']
	num_replicas = 2*num_replicas + 1
	return num_replicas

def get_num_clients(config):
	return config['num_client']

def get_test_case_name(config):
	return config['test_case_name']

#config = parse_file("new_failure_tr")
#rep_fail_trigs = get_rep_fail_triggers(config, 1,0)
#print("rep_fail_trigs", rep_fail_trigs)
