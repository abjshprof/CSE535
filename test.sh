#!/bin/bash

filename=$1
num_replicas=$2
num_clients=$3
test_name=$4
if [[ "$filename" == ""  ||  "$num_replicas" == ""  || "$num_clients" == "" || "$test_name" == "" ]];then
	printf "Usage: ./test.sh config_filename num_replicas num_clients test_name\n"
	exit
fi
printf "Got filename $filename , num_replicas $num_replicas, num_clients $num_clients, test_name $test_name\n"
mkdir -p logs
mkdir -p logs/$test_name
LOG_DIR=${PWD}/logs/$test_name
rm -f logs/$test_name/*
cp ./process_files.sh ./logs/$test_name/
rm -f *.da
rm -rf __pycache__
cp ./process_files.sh ./logs/
rm -f olympus.py rep_classes.py client.py central_client.py
cp ./myOlympus.py olympdef.da
cp ./myrep_classes.py rep_classes.da
cp ./myclient.py client.da
cp ./mycentral.py central_client.da
#cp ./myOlympusdef.py olympus.da
cp ./validate_proofs.py validate_proofs.da


olympus_cmd="--tab -e \"bash -c 'python3.5 -m da  -f -F output --logfilename=${LOG_DIR}/olymp_log --message-buffer-size 32768  -n Olympus olympdef.da $filename ; /bin/bash -i' ; exec \$SHELL \" "
central_cmd="--tab -e \"bash -c 'sleep 5; python3.5 -m da -f -F output -D --logfilename=${LOG_DIR}/central_log --message-buffer-size 32768  -n Central_client olympdef.da $filename; /bin/bash -i '  ; exec \$SHELL  \" "

tab="--tab"
foo=""
cmd1="\"bash -c 'sleep 5;python3.5 -m da -f -F output -D  --logfilename=${LOG_DIR}/"
cmd2=" --message-buffer-size 32768  -n "
cmd3=" $filename /bin/bash -i'   ;exec \$SHELL \""
counter=0
client="client"
client_fname="olympdef.da"
while [ $counter -lt $num_clients ]
do
	#echo $counter
	log_name="client${counter}_log"
	node_name="Client$counter"
	sub_cmd="$cmd1$log_name$cmd2$node_name $client_fname$cmd3"
	final_cmd="$final_cmd --tab -e $sub_cmd"
	#echo $sub_cmd
	((counter++))
done

printf "\n\n"
counter=0
rep_fname="olympdef.da"
while [ $counter -lt $num_replicas ]
do
	#echo $counter
	log_name="rep${counter}_log"
	node_name="Replica$counter"
	if (( counter == 0 ))
	then
		log_name="head_log"
		node_name="Head"	
	fi
	
	if (( counter == $num_replicas -1 ))
	then
		log_name="tail_log"
		node_name="Tail"	
	fi

	sub_cmd="$cmd1$log_name$cmd2$node_name $rep_fname$cmd3"
	final_cmd="$final_cmd --tab -e $sub_cmd"
	#echo $sub_cmd
	((counter++))
done

final_cmd="gnome-terminal $olympus_cmd  $central_cmd $final_cmd"
printf "\n\n"
#echo $final_cmd 
echo $final_cmd > run.sh
./run.sh
#chmod +x run.sh
exit 0
