# CACTI Plug-in for Accelergy

An energy estimation plug-in for [Accelergy framework](https://github.com/nelliewu95/accelergy)

## Get started 
- Install [Accelergy framework](https://github.com/nelliewu95/accelergy)
- Download and build [CACTI7](https://github.com/HewlettPackard/cacti) 

## Use the plug-in
- Clone the repo by ```git clone https://github.com/nelliewu95/accelergy-cacti-plug-in.git```
- To set the relative accuracy of your CACTI plug-in
    - open ```cacti_wrapper.py``` 
    - Edit the first line to set the ```CACTI_ACCURACY``` (default is 70)
- Install plug-in
    - Run ```pip3 install .``` and use the same arguments as installing Accelergy 
- Place CACTI7 
    - biuld CACTI7
    - Place the entire source code foler, which contains the cacti binary, inside:
        - the installed plug-in folder (e.g., ```~/.local/share/accelergy/estimation_plug_ins/accelergy-cacti-plug-in```)
        - any folder (or its subfolder) that is included in the ```$PATH```
- Run Accelergy (Accelergy's log will show that it identifies the CACTI plug-in )

