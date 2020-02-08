import argparse, sys, os, psutil, subprocess, re, signal
import logging, logging.handlers
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QTimer
import pkg_resources

import oskb

def main():
    
    #
    # The whole thing is wrapped in a try/except so we can syslog if we're in background
    #
    

    #
    # Parse command line arguments
    #

    ap = argparse.ArgumentParser()
    ap.add_argument('keyboards', help='one or more keyboard files', 
        metavar='<kbd>', nargs='*', default=['phoney-us'])
    ap.add_argument('--left', '-x', help='window left', metavar='<x>', type=int)
    ap.add_argument('--top', '-y', help='window top', metavar='<y>', type=int)  
    ap.add_argument('--width', help='window width', metavar='<width>', type=int)
    ap.add_argument('--height', help='window height', metavar='<height>', type=int)
    ap.add_argument('--vpos', help='vertical position', metavar='top|bottom', 
        choices=['top', 'bottom'], default='bottom')
    ap.add_argument('--hpos', help='horizontal position', metavar='left|center|right',
        choices=['left', 'center', 'right'], default='right')
    ap.add_argument('--toggle', help='toggles oskb on and off', action='store_true')
    ap.add_argument('--off', help='turns oskb off', action='store_true')
    ap.add_argument('--list', help='list built-in keyboards', action='store_true')
    ap.add_argument('--keypipe', '-p', help='filename for keypipe', metavar='<filename>',
        default='/var/run/oskb-keypipe')
    ap.add_argument('--version', '-v', help='print version number and exit', action='store_true')
    cmdline = ap.parse_args()

    if cmdline.version:
        print(pkg_resources.get_distribution('oskb').version)
        sys.exit(0)
        
    if cmdline.list:
        for k in pkg_resources.resource_listdir('oskb', 'keyboards'):
            print(k)
        sys.exit(0)


    #
    # Kill any existing keyboard instances. If we did end up killing existing keyboards
    # only start up if '--toggle' wasn't specified. It allows the same command line to
    # be used to turn the keyboard on and off. '--off' just kills keyboard processes. 
    #

    ikilled = False
    mypid = os.getpid()
    myparent = os.getppid()
    myname = os.path.basename( psutil.Process().name())
    if re.match('^python\d*$', myname):
        myname = os.path.basename( psutil.Process().cmdline()[1] )
    for proc in psutil.process_iter(attrs=(['pid'])):
        if not proc.pid == mypid and not proc.pid == myparent:
            itsname = os.path.basename( proc.name() )
            if re.match('^python\d*$', itsname):
                itsname = os.path.basename( proc.cmdline()[1] )
            if itsname == myname:
                proc.send_signal(9)
                ikilled = True

    if ( ikilled and cmdline.toggle ) or cmdline.off:
        sys.exit()

    
    #
    # Start the Qt context
    #

    app = QApplication([])


    #
    # Make sure Ctrl-C can interrupt oskb
    #

    def sigint_handler(*args):
        sys.stderr.write('\r')
        QApplication.quit()

    signal.signal(signal.SIGINT, sigint_handler)
    timer = QTimer()
    timer.start(250)
    timer.timeout.connect(lambda: None)


    #
    # Get our keyboard instance, and quickly make sure Qt doesn't make a window frame etc.
    #

    keyboard = oskb.Keyboard()

    # Qt.X11BypassWindowManagerHint     : No WM border or title and no application focus
    keyboard.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.X11BypassWindowManagerHint)


    #
    # Tell keyboard where to send the keypresses and what keyboards to load
    #

    keyboard.setKeypipe(cmdline.keypipe)
    keyboard.readKeyboards(cmdline.keyboards)


    #
    # Figure out where and how big we're going to be on the screen
    #

    # See if xprop will give us the workarea minus taskbar and such.
    try:
        out = subprocess.check_output(['xprop','-root','_NET_WORKAREA'])
        workarea = re.split('=|,',out.decode())
        screenleft = int( workarea[1] )
        screentop = int( workarea[2] )
        screenwidth = int( workarea[3] )
        screenheight = int( workarea[4] )
    # If not, use the screen dimensions
    except:
        desktop = app.desktop()
        screen = desktop.screenGeometry()
        screenleft = 0
        screentop = 0
        screenwidth = screen.width()
        screenheight = screen.height()
    # set width and height from arguments, defaulting to screen width and quarter of screen height resp. 
    w = cmdline.width if cmdline.width else screenwidth
    h = cmdline.height if cmdline.height else int( screenheight / 4 )       
    # Vertical position
    if cmdline.top:
        y = cmdline.top
    else:
        if cmdline.vpos == 'bottom':
            y = screentop + screenheight - h
        else:
            y = screentop
    # Horizontal position
    if cmdline.left:
        x = cmdline.left
    else:
        if cmdline.hpos == 'center':
            x = int( screenleft + ( screenwidth / 2 ) - ( w / 2) )
        elif cmdline.hpos == 'left':
            x = screenleft
        else:
            x = screenleft + screenwidth - w

    keyboard.setGeometry(x, y, w, h)


    #
    # Display the keyboard
    #

    keyboard.show()

    sys.exit(app.exec_())