import os
import sys
import argparse
import time
import signal
import math
import random

# include the netbot src directory in sys.path so we can import modules from it.
robotpath = os.path.dirname(os.path.abspath(__file__))
srcpath = os.path.join(os.path.dirname(robotpath),"src")
sys.path.insert(0,srcpath)

from netbots_log import log
from netbots_log import setLogLevel
import netbots_ipc as nbipc
import netbots_math as nbmath

robotName = "Cyrus_Bot3"
enemyX = 0
enemyY = 0
wall = ""
distanceToNearestBot = 0

def scanning(min, max, n):

    if (min < max-1 and wall != "left") or (min > max+1 and wall == "left"):

        scanSlices = 32
        mid = (min+max)/2

        scanSlice1Start = math.pi/16*min
        midSliceRad = math.pi/16*mid
        scanSlice2End = math.pi/16*max

        minScan = scan(scanSlice1Start, midSliceRad)
        minScanDistance = distanceToNearestBot

        maxScan = scan(midSliceRad, scanSlice2End)
        maxScanDistance = distanceToNearestBot

        if minScan and not(maxScan):
            return scanning(min, mid, n+1)
        elif maxScan and not(minScan):
            return scanning(mid, max, n+1)
        elif maxScan and minScan:
            if maxScanDistance > minScanDistance:
                return scanning(min, mid, n+1)
            else:
                return scanning(mid, max, n+1)
        else:
            return -1

    else:

        return (min+max)/2 #?

def scan(scanRadStart, scanRadEnd):

    scanReply = botSocket.sendRecvMessage(
        {'type': 'scanRequest', 'startRadians': scanRadStart, 'endRadians': scanRadEnd})

    # if we found an enemy robot with our scan
    if scanReply['distance'] >= 50:
        getLocationReply = botSocket.sendRecvMessage({'type': 'getLocationRequest'})
        x = getLocationReply['x']
        y = getLocationReply['y']
        angleToNearestBot = (scanRadStart + scanRadEnd)/2
        global enemyX
        global enemyY
        global distanceToNearestBot
        distanceToNearestBot = scanReply['distance']

        enemyX = x + distanceToNearestBot * math.cos(angleToNearestBot)
        enemyY = y + distanceToNearestBot * math.sin(angleToNearestBot)

        return True
    else:
        return False

def reverseDirection(direction, wall):

    if wall == "left" or wall == "right":
        if direction == math.pi/2:
            direction = math.pi * 3/2
        else:
            direction = math.pi/2
    elif wall == "up" or wall == "down":
        if direction == math.pi:
            direction = 0
        else:
            direction = math.pi

    return direction

def play(botSocket, srvConf):
    gameNumber = 0  # The last game number bot got from the server (0 == no game has been started)

    while True:
        try:
            # Get information to determine if bot is alive (health > 0) and if a new game has started.
            getInfoReply = botSocket.sendRecvMessage({'type': 'getInfoRequest'})
        except nbipc.NetBotSocketException as e:
            # We are always allowed to make getInfoRequests, even if our health == 0. Something serious has gone wrong.
            log(str(e), "FAILURE")
            log("Is netbot server still running?")
            quit()

        if getInfoReply['health'] == 0:
            # we are dead, there is nothing we can do until we are alive again.
            continue

        if getInfoReply['gameNumber'] != gameNumber:
            # A new game has started. Record new gameNumber and reset any variables back to their initial state
            gameNumber = getInfoReply['gameNumber']
            log("Game " + str(gameNumber) + " has started. Points so far = " + str(getInfoReply['points']))

            maxSpeed = 70
            reversing = False
            scanCounter = 0
            defensiveScan = False
            counter = 0
            direction = 0
            speed = 50
            startingDirection = True
            global wall
            wall = ""
            currentMode = "scan"
            scanSlices = 32
            nextScanSlice = 0
            scanSliceWidth = math.pi * 2 / scanSlices
            maxScanSlice = 0
            minScanSlice = 0

            getLocationReply = botSocket.sendRecvMessage({'type': 'getLocationRequest'})
            x = getLocationReply['x']
            y = getLocationReply['y']

            # run to nearest wall from starting location
            if x < 500 and y < 500:
                if x >= y:
                    direction = math.pi * 3/2
                    wall = "down"
                else:
                    direction = math.pi
                    wall = "left"
            elif x < 500 and y >= 500:
                if x >= 1000-y:
                    direction = math.pi/2
                    wall = "up"
                else:
                    direction = math.pi
                    wall = "left"
            elif x >= 500 and y < 500:
                if 1000-x <= y:
                    direction = 0
                    wall = "right"
                else:
                    direction = math.pi * 3/2
                    wall = "down"
            elif x >= 500 and y >= 500:
                if x >= y:
                    direction = 0
                    wall = "right"
                else:
                    direction  = math.pi/2
                    wall = "up"

        try:

            getLocationReply = botSocket.sendRecvMessage({'type': 'getLocationRequest'})
            x = getLocationReply['x']
            y = getLocationReply['y']
            getSpeedReply = botSocket.sendRecvMessage({'type': 'getSpeedRequest'})

            if getSpeedReply['currentSpeed'] == 0:

                if not(startingDirection):
                    direction = reverseDirection(direction, wall)
                if counter >= 1:
                    startingDirection = False

                # Turn in a new direction
                botSocket.sendRecvMessage({'type': 'setDirectionRequest', 'requestedDirection': direction})

                speed = maxSpeed

                # log some useful information.
                log("Requested to go " + str(direction/math.pi) + " pi radians at speed: " + str(speed), "INFO")
                botSocket.sendRecvMessage({'type': 'setSpeedRequest', 'requestedSpeed': speed})
                reversing = False

            elif not(reversing):

                if startingDirection:
                    if (x <= 100 and direction == math.pi) or (x >= 900 and direction == 0) or (y <= 100 and direction == math.pi * 3/2) or (y >= 900 and direction == math.pi/2):
                        speed = 10
                else:
                    if (x <= 200 and direction == math.pi) or (x >= 800 and direction == 0) or (y <= 200 and direction == math.pi * 3/2) or (y >= 800 and direction == math.pi/2):
                        speed = 0
                        reversing = True
                    else:
                        speed = maxSpeed

                botSocket.sendRecvMessage({'type': 'setSpeedRequest', 'requestedSpeed': speed})

            if not(startingDirection):
                if currentMode == "wait":
                    # find out if we already have a shell in the air. We need to wait for it to explode before
                    # we fire another shell. If we don't then the first shell will never explode!
                    getCanonReply = botSocket.sendRecvMessage({'type': 'getCanonRequest'})
                    if not getCanonReply['shellInProgress']:
                        # we are ready to shoot again!
                        currentMode = "scan"

                if currentMode == "scan":

                    defensiveScan = True if scanCounter % 6 == 0 else False

                    # defensive scan
                    if defensiveScan:

                        scanSliceTemp = nextScanSlice

                        scanRadStart = nbmath.normalizeAngle(direction - math.pi/4)
                        scanRadEnd = nbmath.normalizeAngle(direction + math.pi/4)

                        if scan(scanRadStart, scanRadEnd):
                            # i made this as two different if statements because we are setting distanceToNearestBot within scan
                            if distanceToNearestBot < 200:
                                reverseDirection(direction, wall)

                    else:

                        scanning(minScanSlice, maxScanSlice, 1)

                        if (distanceToNearestBot > 150):
                            getLocationReply = botSocket.sendRecvMessage({'type': 'getLocationRequest'})
                            x = getLocationReply['x']
                            y = getLocationReply['y']

                            botSocket.sendRecvMessage(
                                {'type': 'fireCanonRequest', 'direction': nbmath.angle(x, y, enemyX, enemyY), 'distance': nbmath.distance(x, y, enemyX, enemyY)})
                            currentMode = "wait"

                    scanCounter += 1

            # initialize starting scan slice
            else:
                if wall == "up":
                    minScanSlice = 16
                    maxScanSlice = 32
                elif wall == "left":
                    minScanSlice = 24
                    maxScanSlice = 8
                elif wall == "down":
                    minScanSlice = 0
                    maxScanSlice = 16
                elif wall == "right":
                    minScanSlice = 8
                    maxScanSlice = 24

            counter += 1

        except nbipc.NetBotSocketException as e:
            # Consider this a warning here. It may simply be that a request returned
            # an Error reply because our health == 0 since we last checked. We can
            # continue until the next game starts.
            log(str(e), "WARNING")
            continue

##################################################################
# Standard stuff below.
##################################################################


def quit(signal=None, frame=None):
    global botSocket
    log(botSocket.getStats())
    log("Quiting", "INFO")
    exit()


def main():
    global botSocket  # This is global so quit() can print stats in botSocket
    global robotName

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-ip', metavar='My IP', dest='myIP', type=nbipc.argParseCheckIPFormat, nargs='?',
                        default='127.0.0.1', help='My IP Address')
    parser.add_argument('-p', metavar='My Port', dest='myPort', type=int, nargs='?',
                        default=20010, help='My port number')
    parser.add_argument('-sip', metavar='Server IP', dest='serverIP', type=nbipc.argParseCheckIPFormat, nargs='?',
                        default='127.0.0.1', help='Server IP Address')
    parser.add_argument('-sp', metavar='Server Port', dest='serverPort', type=int, nargs='?',
                        default=20000, help='Server port number')
    parser.add_argument('-debug', dest='debug', action='store_true',
                        default=False, help='Print DEBUG level log messages.')
    parser.add_argument('-verbose', dest='verbose', action='store_true',
                        default=False, help='Print VERBOSE level log messages. Note, -debug includes -verbose.')
    args = parser.parse_args()
    setLogLevel(args.debug, args.verbose)

    try:
        botSocket = nbipc.NetBotSocket(args.myIP, args.myPort, args.serverIP, args.serverPort)
        joinReply = botSocket.sendRecvMessage({'type': 'joinRequest', 'name': robotName}, retries=300, delay=1, delayMultiplier=1)
    except nbipc.NetBotSocketException as e:
        log("Is netbot server running at" + args.serverIP + ":" + str(args.serverPort) + "?")
        log(str(e), "FAILURE")
        quit()

    log("Join server was successful. We are ready to play!")

    # the server configuration tells us all about how big the arena is and other useful stuff.
    srvConf = joinReply['conf']
    log(str(srvConf), "VERBOSE")

    # Now we can play, but we may have to wait for a game to start.
    play(botSocket, srvConf)


if __name__ == "__main__":
    # execute only if run as a script
    signal.signal(signal.SIGINT, quit)
    main()
