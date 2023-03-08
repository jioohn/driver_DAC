# -*- coding: utf-8 -*-
"""
Created on Fri Nov 23 15:02:11 2018

@author: Xavier Jehl
"""
import time
import logging
import numpy as np
import visa  # used for the parity constant
import traceback
import threading

from qcodes import  validators as vals
from qcodes.utils.validators import Enum, Strings,Bool, Numbers
from qcodes import VisaInstrument


#dmm ip  TCPIP0::K-34461A-12520.local::inst0::INSTR


#def then(self, *actions, overwrite=False):
#        """
#        Attach actions to be performed after the loop completes.
#        These can only be ``Task`` and ``Wait`` actions, as they may not generate
#        any data.
#        returns a new Loop object - the original is untouched
#        This is more naturally done to an ActiveLoop (ie after .each())
#        and can also be done there, but it's allowed at this stage too so that
#        you can define final actions and share them among several ``Loops`` that
#        have different loop actions, or attach final actions to a Loop run
#        TODO:
#            examples of this ? with default actions.
#        Args:
#            *actions: ``Task`` and ``Wait`` objects to execute in order
#            overwrite: (default False) whether subsequent .then() calls (including
#                calls in an ActiveLoop after .then() has already been called on
#                the Loop) will add to each other or overwrite the earlier ones.
#        Returns:
#            a new Loop object - the original is untouched
#        """
#        return _attach_then_actions(self._copy(), actions, overwrite)


class ITest(VisaInstrument):
  
    def __init__(self, name, address, dac_step=10e-3, dac_delay=.01, **kwargs):
        super().__init__(name, address, terminator='\n', **kwargs)

        idn = self.IDN.get()
#startstop works but gives an error, does not receive feedback that say the process it's over
        self.add_parameter('start',
                           get_cmd='outp on',
                           get_parser=float,
                         )
        
        
        self.add_parameter('stop',
                           get_cmd='outp off',
                           get_parser=float,
                         )
#        self.add_parameter('resolution',
#                           get_cmd='VOLT:DC:RES?',
#                           get_parser=float,
#                           set_cmd='VOLT:DC:RES'  + ' {:.4f}',
#                           set_parser=float,
#                           label='Resolution',
#                           unit='V')
        
        self.add_parameter('volt',
                           get_cmd='i1;c1;VOLT?',
                           set_cmd='i1;c1;VOLT' + ' {:.8f}',
                           label='Voltage',
                           get_parser=float,
                           unit='V')
        self.add_parameter('check_setpoints',
                           get_cmd=None, set_cmd=None,
                           initial_value=False,
                           label='Check setpoints',
                           vals=Bool(),
                           docstring=('Whether to check if the setpoint is the'
                                      ' same as the current DAC value to '
                                      'prevent an unnecessary set command.'))

        # Time to wait before sending a set DAC command to the IVVI
        self.add_parameter('dac_set_sleep',
                           get_cmd=None, set_cmd=None,
                           initial_value=0.01,
                           label='DAC set sleep',
                           unit='s',
                           vals=Numbers(0),
                           docstring=('When check_setpoints is set to True, '
                                      'this is the waiting time between the'
                                      'command that checks the current DAC '
                                      'values and the final set DAC command'))
        self.add_parameter('dac_read_buffer_sleep',
                           get_cmd=None, set_cmd=None,
                           initial_value=0.01,
                           label='DAC read buffer sleep',
                           unit='s',
                           vals=Numbers(0),
                           docstring=('While receiving bytes from the IVVI, '
                                      'sleeping is done in multiples of this '
                                      'value. Change to a lower value for '
                                      'a shorter minimum time to wait.'))
#        self.add_parameter('setdac',
#                get_cmd=None, set_cmd=self._gen_dac_set_func(self._set_dac, i),
#                get_parser=float,
#                set_parser=float,
#                label='Dac {}'.format(i+1),
#                unit='V',
#                vals=vals.Numbers(-12,12),
#                docstring=('setdac with ramp mode'))
        
        self.add_parameter(
                'dac17',
                get_cmd='i5;VOLT?',
                set_cmd='i5;VOLT' + ' {:.8f}', #self.write('trig:in:init')
               # set_cmd=self._gen_dac_set_func(self._set_dac, i),
                get_parser=float,
                set_parser=float,
                label='DCsource',
                unit='V',
                step=dac_step,
                inter_delay=dac_delay,
                vals=vals.Numbers(-50,50)
                )
        self.add_parameter(
                'rampdac17',
                get_cmd='i5;VOLT?',
                set_cmd=self._gen_dac_set_func(self._set_dac, 16),
                get_parser=float,
                set_parser=float,
                label='DCsource',
                unit='V',
                vals=vals.Numbers(-50,50)
                )
        
        
        
        numdacs=16
        #create dacs parameters
        for i in range(0, numdacs):
            self.add_parameter(
                'dac{}'.format(i+1),
                get_cmd='i'+str(int(i/4+1))+';c'+str(i%4+1)+';VOLT?',
                set_cmd='i'+str(int(i/4+1))+';c'+str(i%4+1)+';VOLT' + ' {:.8f}', #self.write('trig:in:init')
               # set_cmd=self._gen_dac_set_func(self._set_dac, i),
                get_parser=float,
                set_parser=float,
                label='Dac {}'.format(i+1),
                unit='V',
                step=dac_step,
                inter_delay=dac_delay,                    
                vals=vals.Numbers(-3,3)
                )
            self.add_parameter(
                'rampdac{}'.format(i+1),
                get_cmd='i'+str(int(i/4+1))+';c'+str(i%4+1)+';VOLT?',
#                set_cmd='i'+str(int(i/4+1))+';c'+str(i%4+1)+';VOLT' + ' {:.8f}', #self.write('trig:in:init')
                set_cmd=self._gen_dac_set_func(self._set_dac, i),
                get_parser=float,
                set_parser=float,
                label='Dac {}'.format(i+1),
                unit='mV',
                vals=vals.Numbers(-3,3)
#                slope=1e-5,#V/ms
#                delay=0.1#ms
                )
            
            ##########################################################################•
            #set the trigger mode for each dac
#           Sets how to perform the output voltage settling. Can be modified when source is OFF.
#EXP (0): exponential settling, immediate actuation
#RAMP (1): ramp settling according to VOLTage:SLOPE, on trigger input event
#+TRIG:DELAY
#STAIR (2): staircase using VOLT:STEP:WIDth and VOLT:STEP:AMPL
#starts after one trigger input event +TRIG:DELAY
#STEP (3): staircase using VOLT:STEP:AMPL, each step is triggered
#by a trigger input event + TRIG:DELAY
#AUTO(4): staircase using VOLT:STEP:AMPL, each step is triggered when settling within
#TRIG:READY:AMPL of the current voltage setting +TRIG:DELAY, starts after
#one trigger input event +TRIG:DELAY          
            eval('self.write("i%d;c%d;trig:in 0")' % (int(i/4+1), int(i%4+1)))
#            by default I initialize in exponential mode that gives a fast loop without triiger control at each step
            #eval('self.dac%d.add_parameter("slope",set_cmd="i%d;c%d;VOLT:SLOP {:.8f}",get_cmd="i%d;c%d;VOLT:SLOP?",unit="V/ms",get_parser=float,set_parser=float,vals=vals.Numbers(1.2e-6, 0.1))' %  (int(i+1), int(i/4+1), int(i%4+1), int(i/4+1), int(i%4+1)))
            #set parameter to control slopes
            self.add_parameter(
                'slope{}'.format(i+1),
                get_cmd='i'+str(int(i/4+1))+';c'+str(i%4+1)+';VOLT:slop?',
                set_cmd='i'+str(int(i/4+1))+';c'+str(i%4+1)+';VOLT:slop' + ' {:.8f}',
                get_parser=float,
                set_parser=float,
                label='Slope{}'.format(i+1),
                unit='V/ms',
                #for security max slope=1V/s
                vals=vals.Numbers(1.3e-6,0.0001)
                
#                slope=1e-5,#V/ms
#                delay=0.1#ms
                )
        self._time_last_update = 0     
        self.add_parameter('dac_voltages',
                           label='Dac voltages',
                           get_cmd=self._get_dacs)
        self.add_parameter('all_slopes',
                           label='Slopes',
                           get_cmd=self._get_slopes,
                           set_cmd=self._set_slopes)


        self.connect_message()
        

    def _gen_dac_set_func(self, fun, i):
        def set_func(val):
            return fun(i, val)
        return set_func
    
    def _set_dac(self, i, val):
        #it is a procedure to wait till the command finish to be executed
        #meaning evaluate trigger status
       dacId = 'i%d;c%d;' % (int(i/4+1), int(i%4+1))
       
       if i==16:
           dacId='i5'
       if bool(int(self.ask(dacId+ 'outp?'))): 
          #go to the ramp mode
          self.write('trig:in 1')
          if bool(int(self.ask(dacId + 'trig:ready?'))):
            self.write('VOLT %.8f' % (val))
            self.write('trig:in:del0')
#            self.write('trig:in:del10')
            self.write('trig:in:init')
#            print('run')  
#            time.sleep(0.001)
          while not bool(int(self.ask(dacId + 'trig:ready?'))):
#              print('waiting')
              time.sleep(0.001) 

       else :
         print('ERROR: turn on the dac %d' %i)
         #after finishing go back to exponential mode
       self.write('trig:in 0') 
       
#       
#    def _set_dac17(self, val):
#        #it is a procedure to wait till the command finish to be executed
#        #meaning evaluate trigger status
#       dacId = 'i5'
#       if bool(int(self.ask(dacId+ 'outp?'))): 
#          #go to the ramp mode
#          self.write('trig:in 1')
#          if bool(int(self.ask(dacId + 'trig:ready?'))):
#            self.write('VOLT %.8f' % (val))
#            self.write('trig:in:del0')
##            self.write('trig:in:del10')
#            self.write('trig:in:init')
##            print('run')  
##            time.sleep(0.001)
#          while not bool(int(self.ask(dacId + 'trig:ready?'))):
##              print('waiting')
#              time.sleep(0.001)
              
              
              
    def _get_slopes(self):
        self._slopes=[]
        numdacs=16
        for i in range(0,numdacs):
                  dac=eval(str('self.slope{}'.format(i+1))+str('.get()'))
                  self._slopes.append(dac)
#                 get_cmd='i'+str(int(i/4+1))+';c'+str(i%4+1)+';VOLT?',
#                 self._voltages[i]=get_cmd
#                  time.sleep(0.01)
        return self._slopes
    

        
    def _set_slopes(self,val):
         numdacs=16
         for i in range(0,numdacs): 
                  eval(str('self.slope{}'.format(i+1))+str('.set(val)'))
    
    def _get_dacs(self):
        '''
        Reads from device and returns all dacvoltages in a list

       Modified from IVVI no time parameter

        Output:
            voltages (float[]) : list containing all dacvoltages (in mV)

        get dacs command takes ~450ms according to ipython timeit
        '''
        numdacs=16
        self._voltages=[]
        for i in range(0,numdacs):
                  dac=eval(str('self.dac{}'.format(i+1))+str('.get()'))
                  self._voltages.append(dac)
#                 get_cmd='i'+str(int(i/4+1))+';c'+str(i%4+1)+';VOLT?',
#                 self._voltages[i]=get_cmd
#                  time.sleep(0.01)
        return self._voltages
    
    def set_dacs_zero(self):
        numdacs=16
        for i in range(0,numdacs): 
                  eval(str('self.rampdac{}'.format(i+1))+str('.set(0)'))
                  self.write('trig:in:init')
        
        
        
        
        
        
    def init_measurement(self):
        self.write('INIT')



    def reset(self):
        self.write('*RST')
        


#iTest.write('outp off')
#iTest.write('outp on')
#iTest.rampdac1(0)
#iTest.rampdac5(0.020)
#iTest.rampdac3(-1)
#iTest.ask('trig:in ?')
#iTest.write('volt:step:ampl 0.001 ')
#
#iTest.write('trig:in:del100')
#
#iTest.write('trig:in 0')#immediate jump
#iTest.write('trig:in 1')
#
#
#
#
#iTest.write('trig:in:init')    
#iTest.ask('i1;c1;trig:ready?')
#
#iTest.ask('i1;c3;trig:ready?')
# 
##iTest.ask('trig:in?')  
        
        
        
        
class ITestfast(VisaInstrument):
  
    def __init__(self, name, address, dac_step=3e-3, dac_delay=10e-6, **kwargs):
        super().__init__(name, address, terminator='\n', **kwargs)

        idn = self.IDN.get()
#startstop works but gives an error, does not receive feedback that say the process it's over
        self.add_parameter('start',
                           get_cmd='outp on',
                           get_parser=float,
                         )
        
        
        self.add_parameter('stop',
                           get_cmd='outp off',
                           get_parser=float,
                         )
#        self.add_parameter('resolution',
#                           get_cmd='VOLT:DC:RES?',
#                           get_parser=float,
#                           set_cmd='VOLT:DC:RES'  + ' {:.4f}',
#                           set_parser=float,
#                           label='Resolution',
#                           unit='V')
        
        self.add_parameter('volt',
                           get_cmd='i1;c1;VOLT?',
                           set_cmd='i1;c1;VOLT' + ' {:.8f}',
                           label='Voltage',
                           get_parser=float,
                           unit='V')
        self.add_parameter('check_setpoints',
                           get_cmd=None, set_cmd=None,
                           initial_value=False,
                           label='Check setpoints',
                           vals=Bool(),
                           docstring=('Whether to check if the setpoint is the'
                                      ' same as the current DAC value to '
                                      'prevent an unnecessary set command.'))

        # Time to wait before sending a set DAC command to the IVVI
        self.add_parameter('dac_set_sleep',
                           get_cmd=None, set_cmd=None,
                           initial_value=0.01,
                           label='DAC set sleep',
                           unit='s',
                           vals=Numbers(0),
                           docstring=('When check_setpoints is set to True, '
                                      'this is the waiting time between the'
                                      'command that checks the current DAC '
                                      'values and the final set DAC command'))
        self.add_parameter('dac_read_buffer_sleep',
                           get_cmd=None, set_cmd=None,
                           initial_value=0.01,
                           label='DAC read buffer sleep',
                           unit='s',
                           vals=Numbers(0),
                           docstring=('While receiving bytes from the IVVI, '
                                      'sleeping is done in multiples of this '
                                      'value. Change to a lower value for '
                                      'a shorter minimum time to wait.'))
#        self.add_parameter('setdac',
#                get_cmd=None, set_cmd=self._gen_dac_set_func(self._set_dac, i),
#                get_parser=float,
#                set_parser=float,
#                label='Dac {}'.format(i+1),
#                unit='V',
#                vals=vals.Numbers(-12,12),
#                docstring=('setdac with ramp mode'))
        
        self.add_parameter(
                'dac17',
                get_cmd='i5;VOLT?',
                set_cmd='i5;VOLT' + ' {:.8f}', #self.write('trig:in:init')
               # set_cmd=self._gen_dac_set_func(self._set_dac, i),
                get_parser=float,
                set_parser=float,
                label='DCsource',
                unit='V',
                step=dac_step,
                inter_delay=dac_delay,
                vals=vals.Numbers(-50,50)
                )
        self.add_parameter(
                'rampdac17',
                get_cmd='i5;VOLT?',
                set_cmd=self._gen_dac_set_func(self._set_dac, 16),
                get_parser=float,
                set_parser=float,
                label='DCsource',
                unit='V',
                vals=vals.Numbers(-50,50)
                )
        
        
        
        numdacs=16
        #create dacs parameters
        for i in range(0, numdacs):
            self.add_parameter(
                'dac{}'.format(i+1),
                get_cmd='i'+str(int(i/4+1))+';c'+str(i%4+1)+';VOLT?',
                set_cmd='i'+str(int(i/4+1))+';c'+str(i%4+1)+';VOLT' + ' {:.8f}', #self.write('trig:in:init')
               # set_cmd=self._gen_dac_set_func(self._set_dac, i),
                get_parser=float,
                set_parser=float,
                label='Dac {}'.format(i+1),
                unit='V',
                step=dac_step,
                inter_delay=dac_delay,                    
                vals=vals.Numbers(3,3)
                )
            self.add_parameter(
                'rampdac{}'.format(i+1),
                get_cmd='i'+str(int(i/4+1))+';c'+str(i%4+1)+';VOLT?',
#                set_cmd='i'+str(int(i/4+1))+';c'+str(i%4+1)+';VOLT' + ' {:.8f}', #self.write('trig:in:init')
                set_cmd=self._gen_dac_set_func(self._set_dac, i),
                get_parser=float,
                set_parser=float,
                label='Dac {}'.format(i+1),
                unit='mV',
                vals=vals.Numbers(-3,3)
#                slope=1e-5,#V/ms
#                delay=0.1#ms
                )
            
            ##########################################################################•
            #set the trigger mode for each dac
#           Sets how to perform the output voltage settling. Can be modified when source is OFF.
#EXP (0): exponential settling, immediate actuation
#RAMP (1): ramp settling according to VOLTage:SLOPE, on trigger input event
#+TRIG:DELAY
#STAIR (2): staircase using VOLT:STEP:WIDth and VOLT:STEP:AMPL
#starts after one trigger input event +TRIG:DELAY
#STEP (3): staircase using VOLT:STEP:AMPL, each step is triggered
#by a trigger input event + TRIG:DELAY
#AUTO(4): staircase using VOLT:STEP:AMPL, each step is triggered when settling within
#TRIG:READY:AMPL of the current voltage setting +TRIG:DELAY, starts after
#one trigger input event +TRIG:DELAY          
            eval('self.write("i%d;c%d;trig:in 0")' % (int(i/4+1), int(i%4+1)))
#            by default I initialize in exponential mode that gives a fast loop without triiger control at each step
            #eval('self.dac%d.add_parameter("slope",set_cmd="i%d;c%d;VOLT:SLOP {:.8f}",get_cmd="i%d;c%d;VOLT:SLOP?",unit="V/ms",get_parser=float,set_parser=float,vals=vals.Numbers(1.2e-6, 0.1))' %  (int(i+1), int(i/4+1), int(i%4+1), int(i/4+1), int(i%4+1)))
            #set parameter to control slopes
            self.add_parameter(
                'slope{}'.format(i+1),
                get_cmd='i'+str(int(i/4+1))+';c'+str(i%4+1)+';VOLT:slop?',
                set_cmd='i'+str(int(i/4+1))+';c'+str(i%4+1)+';VOLT:slop' + ' {:.8f}',
                get_parser=float,
                set_parser=float,
                label='Slope{}'.format(i+1),
                unit='V/ms',
                #for security max slope=1V/s
                vals=vals.Numbers(1.3e-6,0.0001)
                
#                slope=1e-5,#V/ms
#                delay=0.1#ms
                )
        self._time_last_update = 0     
        self.add_parameter('dac_voltages',
                           label='Dac voltages',
                           get_cmd=self._get_dacs)
        self.add_parameter('all_slopes',
                           label='Slopes',
                           get_cmd=self._get_slopes,
                           set_cmd=self._set_slopes)


        self.connect_message()
        

    def _gen_dac_set_func(self, fun, i):
        def set_func(val):
            return fun(i, val)
        return set_func
    
    def _set_dac(self, i, val):
        #it is a procedure to wait till the command finish to be executed
        #meaning evaluate trigger status
       dacId = 'i%d;c%d;' % (int(i/4+1), int(i%4+1))
       
       if i==16:
           dacId='i5'
       if bool(int(self.ask(dacId+ 'outp?'))): 
          #go to the ramp mode
          self.write('trig:in 1')
          if bool(int(self.ask(dacId + 'trig:ready?'))):
            self.write('VOLT %.8f' % (val))
            self.write('trig:in:del0')
#            self.write('trig:in:del10')
            self.write('trig:in:init')
#            print('run')  
#            time.sleep(0.001)
          while not bool(int(self.ask(dacId + 'trig:ready?'))):
#              print('waiting')
              time.sleep(0.001) 

       else :
         print('ERROR: turn on the dac %d' %i)
         #after finishing go back to exponential mode
       self.write('trig:in 0') 
       
#       
#    def _set_dac17(self, val):
#        #it is a procedure to wait till the command finish to be executed
#        #meaning evaluate trigger status
#       dacId = 'i5'
#       if bool(int(self.ask(dacId+ 'outp?'))): 
#          #go to the ramp mode
#          self.write('trig:in 1')
#          if bool(int(self.ask(dacId + 'trig:ready?'))):
#            self.write('VOLT %.8f' % (val))
#            self.write('trig:in:del0')
##            self.write('trig:in:del10')
#            self.write('trig:in:init')
##            print('run')  
##            time.sleep(0.001)
#          while not bool(int(self.ask(dacId + 'trig:ready?'))):
##              print('waiting')
#              time.sleep(0.001)
              
              
              
    def _get_slopes(self):
        self._slopes=[]
        numdacs=16
        for i in range(0,numdacs):
                  dac=eval(str('self.slope{}'.format(i+1))+str('.get()'))
                  self._slopes.append(dac)
#                 get_cmd='i'+str(int(i/4+1))+';c'+str(i%4+1)+';VOLT?',
#                 self._voltages[i]=get_cmd
#                  time.sleep(0.01)
        return self._slopes
    

        
    def _set_slopes(self,val):
         numdacs=16
         for i in range(0,numdacs): 
                  eval(str('self.slope{}'.format(i+1))+str('.set(val)'))
    
    def _get_dacs(self):
        '''
        Reads from device and returns all dacvoltages in a list

       Modified from IVVI no time parameter

        Output:
            voltages (float[]) : list containing all dacvoltages (in mV)

        get dacs command takes ~450ms according to ipython timeit
        '''
        numdacs=16
        self._voltages=[]
        for i in range(0,numdacs):
                  dac=eval(str('self.dac{}'.format(i+1))+str('.get()'))
                  self._voltages.append(dac)
#                 get_cmd='i'+str(int(i/4+1))+';c'+str(i%4+1)+';VOLT?',
#                 self._voltages[i]=get_cmd
#                  time.sleep(0.01)
        return self._voltages
    
    def set_dacs_zero(self):
        numdacs=16
        for i in range(0,numdacs): 
                  eval(str('self.rampdac{}'.format(i+1))+str('.set(0)'))
                  self.write('trig:in:init')
        
        
        
        
        
        
    def init_measurement(self):
        self.write('INIT')



    def reset(self):
        self.write('*RST')
        


#iTest.write('outp off')
#iTest.write('outp on')
#iTest.rampdac1(0)
#iTest.rampdac5(0.020)
#iTest.rampdac3(-1)
#iTest.ask('trig:in ?')
#iTest.write('volt:step:ampl 0.001 ')
#
#iTest.write('trig:in:del100')
#
#iTest.write('trig:in 0')#immediate jump
#iTest.write('trig:in 1')
#
#
#
#
#iTest.write('trig:in:init')    
#iTest.ask('i1;c1;trig:ready?')
#
#iTest.ask('i1;c3;trig:ready?')
# 
##iTest.ask('trig:in?')  
        
        
        
        


