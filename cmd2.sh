rm -f logs/*_log
rm -f *.da
mkdir -p logs
rm -rf logs/$1
mkdir -p logs/$1
cp ./src/*.py .
cp ./config/$1 .
cp ./process_files.sh ./logs/
cp ./myOlympus.py olympdef.da
cp ./myrep_classes.py rep_classes.da
cp ./myclient.py client.da
cp ./mycentral.py central_client.da
#cp ./myOlympusdef.py olympus.da
cp ./validate_proofs.py validate_proofs.da
printf $1
python3.5 -m da -F output -f --logfilename=${PWD}/logs/olymp_log --message-buffer-size 327684  -n Olympus olympdef.da $1



#gnome-terminal --tab -e "bash -c 'sleep 2;python3.5 -m da -f -F output  --logfilename=${PWD}/logs/head_log --message-buffer-size 16384  -n Head classdefs.da ';$SHELL" --tab -e "bash -c 'sleep 3; python3.5 -m da -f -F output --logfilename=${PWD}/logs/client_log --message-buffer-size 16384 -D -n Client0 client.da' ;$SHELL" --tab -e  "bash -c 'sleep 3 ;python3.5 -m da -f -F output --logfilename=${PWD}/logs/rep1_log --message-buffer-size 16384 -D -n Replica1 classdefs.da' ;$SHELL" --tab -e "bash -c 'sleep 3 ;python3.5 -m da -f -F output --logfilename=${PWD}/logs/tail_log --message-buffer-size 16384 -D -n Tail classdefs.da ';$SHELL"
