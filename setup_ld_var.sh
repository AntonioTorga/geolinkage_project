#!/usr/bin/bash

FINAL_FOLDER="/etc/ld.so.conf.d"
FILE_NAME="geolinkage_grass_ld_var.conf"
LD_LIB_PATH=$(grass83 --config path)/lib

echo "  Setting Environment Var: LD_LIBRARY_PATH"
echo "  GRASS Lib Folder: $LD_LIB_PATH"
echo "  Config File: $FINAL_FOLDER/$FILE_NAME"
echo " "
echo " Executing [ldconfig] command..."
sudo sh -c "ldconfig"
echo " "

export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$LD_LIB_PATH
sudo sh -c "echo \"$LD_LIB_PATH\" >> $FINAL_FOLDER/$FILE_NAME"
