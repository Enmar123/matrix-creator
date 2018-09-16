import os # Miscellaneous operating system interface
import zmq # Asynchronous messaging framework
import time # Time access and conversions
from random import randint # Random numbers
import sys # System-specific parameters and functions
from matrix_io.proto.malos.v1 import driver_pb2 # MATRIX Protocol Buffer driver library
from matrix_io.proto.malos.v1 import io_pb2 # MATRIX Protocol Buffer sensor library
from multiprocessing import Process, Manager, Value # Allow for multiple processes at once
from zmq.eventloop import ioloop, zmqstream# Asynchronous events through ZMQ
from ledimage import ImageCreator

# Our own imports
from hero import Hero
from goal import Goal
from lava import Lava
from world import World

matrix_ip = '127.0.0.1' # Local device ip
everloop_port = 20021 # Driver Base port
led_count = 0 # Amount of LEDs on MATRIX device (35 leds for us)


def ping_socket():
    # Define zmq socket
    context = zmq.Context()
    # Create a Pusher socket
    ping_socket = context.socket(zmq.PUSH)
    # Connect to the socket
    ping_socket.connect('tcp://{0}:{1}'.format(matrix_ip, everloop_port+1))
    # Send one ping
    ping_socket.send_string('')

def everloop_error_callback(error):
    # Log error
    print('{0}'.format(error))

def update_socket():
    # Define zmq socket
    context = zmq.Context()
    # Create a Subscriber socket
    socket = context.socket(zmq.SUB)
    # Connect to the Data Update port
    socket.connect('tcp://{0}:{1}'.format(matrix_ip, everloop_port+3))
    # Connect Subscriber to Error port
    socket.setsockopt(zmq.SUBSCRIBE, b'')
    # Create the stream to listen to data from port
    stream = zmqstream.ZMQStream(socket)

    # Function to update LED count and close connection to the Data Update Port
    def updateLedCount(data):
        # Extract data and pass into led_count global variable
        global led_count
        led_count = io_pb2.LedValue().FromString(data[0]).green
        # Log LEDs
        print('{0} LEDs counted'.format(led_count))
        # If LED count obtained
        if led_count > 0:
            # Close Data Update Port connection
            ioloop.IOLoop.instance().stop()
            print('LED count obtained. Disconnecting from data publisher {0}'.format(everloop_port+3))
    # Call updateLedCount() once data is received
    stream.on_recv(updateLedCount)

    # Log and begin event loop for ZMQ connection to Data Update Port
    print('Connected to data publisher with port {0}'.format(everloop_port+3))
    ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    # Initiate asynchronous events
    ioloop.install()
    # Start Error Port connection
    # Process(target=register_error_callback, args=(everloop_error_callback, matrix_ip, everloop_port)).start()    
    # Ping the Keep-alive Port once
    ping_socket()
    # Start Data Update Port connection & close after response
    update_socket()
    # Send Base Port configuration
    try:
        context = zmq.Context()
        # Create a Pusher socket
        socket = context.socket(zmq.PUSH)
        # Connect Pusher to configuration socket
        socket.connect('tcp://{0}:{1}'.format(matrix_ip, everloop_port))
       
        img = ImageCreator()

####################### Loading Objects ###############################
        
        # global vars
        old_pitch = 0
        old_roll = 0
        
        # Create world
        world = World()
        
        # create obstacle
        lava = Lava(15)
        lava1 = Lava(30)
        
        # create hero
        hero = Hero(22)
        hero.vel = 0
        
        #create goal
        goal = Goal()
        goal.width = 4
        
        #for tracking time
        start_time = time.time()
        frame = 0
        
####################### led painting happens here ####################     
        while True:
            # Create a new driver config (for setup purposes)
            driver_config_proto = driver_pb2.DriverConfig()
            img.clear_all()
            
            # Painting obstacles
            img.set_led(int(lava.pos), int(lava.r),int(lava.g),int(lava.b),int(lava.w))
            img.set_led(int(lava1.pos), int(lava1.r),int(lava1.g),int(lava1.b),int(lava1.w))
            
            # Paint Goal
            for i_led, v_led in enumerate(goal.rgb_out()):
                img.set_led(int(goal.pos + i_led), int(v_led[0]), int(v_led[1]), int(v_led[2]), int(v_led[3]) )
            
            # Paint Hero
            img.set_led(int(hero.pos), int(hero.r),int(hero.g),int(hero.b),int(hero.w))
            
#####################################################################

            leds = img.out
            image = []
            
           # For each device LED
            for led in leds:
               # Set individual LED value
               ledValue = io_pb2.LedValue()
               ledValue.blue = int(led[2])
               ledValue.red = int(led[0])
               ledValue.green = int(led[1])
               ledValue.white = int(led[3])
               image.append(ledValue)
               
           # Store the Everloop image in driver configuration
            driver_config_proto.image.led.extend(image)
            
            # Send driver configuration through ZMQ socket
            socket.send(driver_config_proto.SerializeToString())
            # Wait before restarting loop
            loop_time = 0.1
            time.sleep(loop_time)
            frame += 1
            
########################game logic happens here#############################################
            
            # Status checks
            hero.check(lava)
            hero.check(lava1)
            hero.check(goal)
            
            # Status behavious
            if hero.won:
                hero.vel = 0
                hero.victoryBlink()
            else:
                 hero.lose_health(255/5*.1)
            
            if hero.dead:
                hero.resurrect()
            
            #Reading imu data
            try:
                world.readFile()
            except:
                world.pitch = old_pitch
                world.roll = old_roll
            
            print(world.pitch)
            print(world.roll)
            
            # object behavior
            hero.speed(world.pitch, world.roll)
            hero.move()
            
            old_pitch = world.pitch
            old_roll = world.roll
            
            lava.pulse()
            lava1.pulse()
            

                

           
#####################################################################
# Avoid logging Everloop errors on user quiting
    except KeyboardInterrupt:
        print(' quit')
