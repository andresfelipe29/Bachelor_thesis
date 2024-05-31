#RingbufQueue
#Addapted from ringbuf_queue.py by peterhinch (Copyright (c) 2016 Peter Hinch)

import _thread
from utime import sleep_ms

class RingbufQueue:
    def __init__(self, buf):
        self._q = [0 for _ in range(buf)] if isinstance(buf, int) else buf
        self._size = len(self._q) #buffer size
        self._wi = 0 #write index
        self._ri = 0 #read index
        self._max_q_size = 100 #biggest buffer size that can be allocated at once

    def full(self): #check if we are overwriting the buffer
        return ((self._wi + 1) % self._size) == self._ri

    def empty(self): #last item read = last saved
        return self._ri == self._wi

    def qsize(self): #number of unread items
        return (self._wi - self._ri) % self._size

    def get_nowait(self):  # Remove and return an item from the queue.
        # Return an item if one is immediately available, else raise QueueEmpty.
        if self.empty():
            raise IndexError
        r = self._q[self._ri]
        self._ri = (self._ri + 1) % self._size
        return r

    def peek(self):  # Return oldest item from the queue without removing it.
        # Return an item if one is immediately available, else raise QueueEmpty.
        if self.empty():
            raise IndexError
        return self._q[self._ri]

    def put_nowait(self, v):
        self._q[self._wi] = v
        self._wi = (self._wi + 1) % self._size
        while self._wi == self._ri:
            sleep_ms(1000)
            v[-1] += 1000 #dead time
            print("core 0 sleeping for 1s because empty")
        return v[-1]

    def put(self, val):
        while self.full():  # Queue full
            print("core 0 sleeping for 1s because full")
            sleep_ms(1000)
            val[-1] += 1000 #dead time
        dead_t = self.put_nowait(val)
        return dead_t

    def __aiter__(self):
        return self

    #allowing the use of a wait routine while data is added, this is addapted to use "update_OLED" as wait routine
    def get(self, wait_routine=None, args=None):
        while self.empty():
            if wait_routine:
                args[0], args[1] = wait_routine(*args)
            else:
                continue
        t_wi = self._wi
        q_size = self.qsize()
        
        if q_size > self._max_q_size:
            t_wi = (self._ri+self._max_q_size) % self._size
            print("big buffer, "+str(q_size)+" unread events")
        else:
            t_wi = self._wi
        
        r = None
        if t_wi > self._ri:
            r = self._q[self._ri:t_wi]
        else:
            r = self._q[self._ri:]+self._q[:t_wi]
        self._ri = t_wi

        if wait_routine:
            wait_r_results = wait_routine(*args)
            return r, wait_r_results
        else:
            return r