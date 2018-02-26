import re
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
	print ("seed", seed, "val",  val, "and types", type(seed), type(val))
	import random
	random.seed(seed)
	for i in range(val):
		idx = random.randint(0,3)
		load_list.append(ops[idx])
	return load_list
		


load_list = generate_pseudo_rand_reqs("pseudorandom(50,50)")
print (load_list)
