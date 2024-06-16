#spectra.py

import utime
import uos, usys
import machine
import _thread
import gc

usys.path.insert(1, r"/drivers/")
import sdcard

#modules
import RingbufQueue

#ADC pins
sgn2 = machine.ADC(26)
TriggerPin = machine.Pin(16, machine.Pin.IN)
TriggerResetPin = machine.Pin(21, machine.Pin.OUT)

b_LED = machine.Pin(14, machine.Pin.OUT)

#buffer to save data
buffer_size = 200
readings = [int] #one ADC measurement per interrupt
event_type = [int]+readings+[int] #saving e_count, adc readings, dead time
buffer = RingbufQueue.RingbufQueue(buffer_size, event_type)
tot_events = 100000

#take turns between "read_ADC" and core0 to access "readings"
interrupt_flag = 1

#data file name
fname = "spectrum.txt"

#total time to take measurements
measure_t = 60 #mins
start_t = utime.ticks_ms()
mins_elapsed = divmod((utime.ticks_diff(utime.ticks_ms(), start_t) // 1000), 60)[0]

#flags to know when to stop measuring
finished0 = False
finished1 = False

def core0_thread():
    global finished0
    global mins_elapsed
    global interrupt_flag
    global buffer
    global readings
    
    e_count = 0
    dead_t = 0
    
    print("measuring")
    interrupt_flag = 0
    
    while mins_elapsed < measure_t:
        
        #check if there is new data to be saved
        if interrupt_flag:    
            
            e_count += 1
            dead_t = buffer.put([e_count]+readings+[dead_t])

            b_LED.off()
            
            #let "read_ADC" know we saved the data in "readings"
            interrupt_flag = 0

        #update time      
        mins_elapsed = divmod((utime.ticks_diff(utime.ticks_ms(), start_t) // 1000), 60)[0]
    
    finished0 = True #let core1 know we are done measuring
    buffer._complete = True #let the buffer now it is complete
    print("0 finished", e_count)
    return

def core1_thread():
    global finished0, finished1
    global mins_elapsed
    global buffer
    
    events = event_type
    prev_min = mins_elapsed

    with open("/sd/"+fname, "w") as file:
        file.write("event,ADC_value[0-65535],dead-time\n")
    
        while not finished0: #check if we are still measuring
        
            events = buffer.get()
            
            if events[0][0]: #write only if there are unread events
                for event in events:
                    data = b"{}\t{}\t{}\n".format(*event)
                    file.write(data)
            
            if mins_elapsed > prev_min:
                file.flush() #save data
                print(mins_elapsed)
                prev_min = mins_elapsed
    
    #let core0 know we are done saving
    finished1 = True
    print("1 finished")
    return

#--------------Micro SD card setup--------------#
# Assign chip select (CS) pin (and start it high)
cs = machine.Pin(5)#GPIO pinout
# Intialize SPI peripheral (start with 1 MHz)
spi = machine.SPI(0,
                  baudrate=1000000,
                  polarity=0,
                  phase=0,
                  bits=8,
                  firstbit=machine.SPI.MSB,
                  #GPIO pinout
                  sck=machine.Pin(2),
                  mosi=machine.Pin(3),
                  miso=machine.Pin(4))
# Initialize SD card
sd = sdcard.SDCard(spi, cs)
# Mount filesystem
vfs = uos.VfsFat(sd)
uos.mount(vfs, "/sd")

#start core1: buffer reader
core1 = _thread.start_new_thread(core1_thread, [])

#interrupt routine
@micropython.native #python decorator for a faster routine
def read_ADC(TriggerPin):
    reading = sgn2.read_u16() #get ADC value
    TriggerResetPin.on() #discharge peak detector capacitor
    TriggerResetPin.off()
    global interrupt_flag
    global readings
    
    #overwrite readings only if previous data was saved
    if interrupt_flag == 0:
        
        #read peak detection
        readings[0] = reading
        b_LED.on()
        
        interrupt_flag = 1 #signal trigger event

#set the interrupt routine with TriggerPin
TriggerPin.irq(trigger=machine.Pin.IRQ_RISING, handler=read_ADC)

utime.sleep_ms(1000)

#start core0: buffer writer, timer
core0_thread()
b_LED.off()

#Wait for core1 to be done before erasing buffer and printing to screen
f0_end_t = utime.ticks_ms()
while not finished1:
    utime.sleep_ms(10)
print("waited for reader thread", utime.ticks_diff(utime.ticks_ms(), f0_end_t), "ms")

#deallocate memory
buffer = None
gc.collect()

print("done")