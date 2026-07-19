#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only
set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

LOCKFILE="/tmp/supi8.lock"

if [ -f "$LOCKFILE" ]; then
    echo "Setup already running or previously crashed."
    exit 1
fi

touch "$LOCKFILE"
trap "rm -f $LOCKFILE" EXIT

run() {
    echo ""
    echo "== $1 =="
    bash "$BASE_DIR/scripts/$2" || {
        echo "FAILED: $2"
        exit 1
    }
}

echo "Starting SuPi-8 installer"

cat << "EOF"
             .                                                             
         @@@@@@@                                                           
    :.#@@@@@@@@@@@@===:                                                    
  :..................           :....:. ..-                                
  :..............................         ::-@@@##@@@@                     
  ::...................................   @@@@@@@@.=+@@                    
 .:::::..................................+@@+@@:@@@:@@:       #%@@@@@      
 .::::::::........SuPi-8................ #@@.%  :  *.   ##*==-@@@@@@@@@:   
 :::::::::::............................ %@@  : +    %%##*+=@@@@@@@@@@@@@  
 :::::::::@@@@@@:....................... @@  :.     %*@@%@@@@@@@@@@@#@@@@- 
 .::::::::@@@@@@:........................@ .- .    @%%@@@@@@@@@@@@@@@@@@@@ 
..@@@-::::@@@@@@........................-@ .      @@@@@@@@@@@@@@@@@@@%@@@@ 
..:@*+@@@@@@@%=@@@......................=@.+.=....@@@@@@@@@@@@@@@@@@@%@@@@ 
...@@*#@@@*+#@@@@@@@@@@@@@**@@@.........:@..:.....@@@@@@@@@@@@@@@@@@@@@@@@ 
....::=@@@=@@@@@@@@@@@@@@@@@:#@@@@@@@@+..@@.-:#::.@@@@@@@@@@@@@@@@@@%@@@@. 
......   .=+:::::.+@@@=@@@*@.@@@@@*:@@#. @@@.--==-:@@@@@@@@@@@@@@@@@@@@@@  
....        :@@@@%@=@@@=::....#@@@=#@@@. @@@@@* ::::-@@@@@@@@@@@@#@@@@@@ ..
...       .%+-@@@@@@@@@@@@@@@@@@@@@-:....+@@%%#%@@      @@@@@@@@@@@@@@@  ..
..       .@@+     %@@@@@@@@@@@@@@@@@@@@@@@@@@@.@#@        @@@@@@@@@@@ .....
. ...... @@%              @@@@@@@@@@@@@@@@%@@@@.             @@@@@. ...... 
........@@%                 :@@@@@@@@@@@@@@@@@%                    .. ..   
.......@@@. .                #@@@@@@@@@@@@@@@@@:                           
.......@@%..                 @@@@@@@@@@@@@@@@                              
.......@@+                   @@@@@@@@@@@@@@@%                              
.......@@+                   @@@@@@@@@@@@@@@@                              
.......@@@                   @@@@@@@@@@@@@@@%                              
::::::..@@%.                 @@@@@@@@@@@@@@@%                              
:::::::::@@@#....       :@@@%@@@@@@@@@@@@@@@%                              
:::::::--=+%@@@%*++*%=.....  @@@@@@@@@@@@@@@%                              
::::::::::::::::-=*@@@@%%%###@@@@@@@@@@@@@@@%                              
......::::::::::::::::::::::+@@@@@@@@@@@@@@@%                              
     .........::::::::::::::-@@@@@@@@@@@@@@@-....                          
            ..........::::---@@@@@@@@@@@@@@@%#-:......                     
                    ........:::-+@@@@@@@@@@@=:::...........                
                                                                                                              
EOF


while true; do
    read -rsp "Enter hotspot password (min 8 chars, leave empty for default 'Classic!'): " HOTSPOT_PASS
    echo ""

    if [ -z "$HOTSPOT_PASS" ]; then
        HOTSPOT_PASS="Classic!"
        echo "Using default password: $HOTSPOT_PASS"
        break
    fi

    read -rsp "Confirm password: " HOTSPOT_PASS_CONFIRM
    echo ""

    if [ "$HOTSPOT_PASS" != "$HOTSPOT_PASS_CONFIRM" ]; then
        echo "Passwords do not match."
    elif [ "${#HOTSPOT_PASS}" -lt 8 ]; then
        echo "Password must be at least 8 characters."
    else
        break
    fi
done

export HOTSPOT_PASS
export HOTSPOT_PASS


run "Clean" clean.sh
run "Storage" storage.sh
run "System" system.sh
run "App" app.sh
run "Services" services.sh
run "Network" network.sh

echo ""

cat << "EOF"

 __    _                                     
/   _ |_)_|_    __ _    |V| _ __  _ __ _|_ _ 
\__(_||   |_|_| | (/_   | |(_)|||(/_| | |__> 
             _         _                   | 
__  _ _|_   |_) _  ___|_ _  _ _|_ o  _ __  | 
| |(_) |_   |  (/_ |  | (/_(_  |_ | (_)| | o 


EOF

echo "Have Fun!"
echo ""


read -r -p "Reboot now? (y/n): " answer

case "$answer" in
    y|Y|yes|YES)
        echo "Rebooting..."
        (sleep 2; reboot) &
        exit 0
        ;;
    *)
        echo "Reboot cancelled. Please reboot manually."
        ;;
esac