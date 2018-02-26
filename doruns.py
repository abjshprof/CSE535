import sys
import subprocess
import shutil

subprocess.call(["./copy.sh"])


print("trying to copy")
config_filename = sys.argv[1]
src="./config/" + config_filename
shutil.copy2(src, '.')

print ("Config file",config_filename)
from read_config import parse_file
from read_config import get_num_replicas
from read_config import get_test_case_name
from read_config import get_num_clients


config = parse_file(config_filename)

num_replicas = get_num_replicas(config)
num_clients = get_num_clients(config)
test_name = get_test_case_name(config)

print ("config_filename",config_filename, "num_replicas", num_replicas, "num_clients", num_clients, "test_name", test_name)

subprocess.call(["./test.sh", config_filename, str(num_replicas), str(num_clients), test_name])
