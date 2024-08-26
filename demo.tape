# Before running vhs with zsh run the command below to set correct prompt
# (unset -v PS1; zsh -f)
# Where should we write the GIF?
Output demo.gif

# Set up a 1000x600 terminal with 12px font.
Set FontSize 16
Set Width 1000
Set Height 600

Sleep 1ms

# Setup
Hide
Type 'alias susscanner="python3 -m susscanner" && clear'
Enter
Type 'alias pip3="echo > /dev/null" && clear'
Enter
Sleep 5ms
Show

Type "pip3 install --upgrade --quiet sustainability-scanner"
Sleep 2s
Enter

# Wait for network - adding hidden delay
Hide
#Sleep 20s
Sleep 2s
Show

Sleep 2s

Type "susscanner --help"
Sleep 2s
Enter

Sleep 2s

Type "susscanner demo_cloudformation.yaml | less"
Sleep 2s
Enter

Sleep 2s

Down 40
Sleep 5s