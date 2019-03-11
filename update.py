import re
import os 
import sys
import time
import paramiko
import subprocess
from multiprocessing import Process


class sshclient:

    def __init__(self, ip_addr, port = 22, username = "", password = " "):

        self.ip_addr = ip_addr
        self.port = port
        self.username = username
        self.password = password
        self.hostkey = None
       
        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(self.ip_addr, self.port, self.username, self.password)
        self.channel = self.client.invoke_shell()
        self.transport = self.client.get_transport()
        self.buffer = ""

    def __del__(self):
        try:
            self.channel.close()
            self.transport.close()

        except:
            pass


    def _read(self):
        try:
            i = 0
            while i < 4:
                if self.channel.recv_ready():
                    self.buffer += self.channel.recv(65535)
                else:
                    time.sleep(0.1)
                    i += 1

        except:
            self.__del__()


    def read_until(self, expected, timeout = 20):
        if not expected:
            return ""

        base_time = time.time()
        while True:
            self._read()
            x = self.buffer.partition(expected)
            if x[1]:
                self.buffer = x[2]
                return "%s%s" % (x[0], x[1])

            if time.time() - base_time > timeout:
                return ""
   
    def write(self, data):
	time.sleep(0.2)
        self.channel.send(data)
	time.sleep(0.2)


    def close(self):
        self.__del__()



class FWUpdate(sshclient):
 
    def __init__(self,ap_ip,fw_name):
        self.ap_ip = ap_ip
        self.fw_name = fw_name
        self.txt = None
        self.te_control_ip = os.environ['TEST_ENGINE_IPV4_ADDR']
        self.Right_password = None
      
    def read_the_output(self,until = "rkscli:",flag = 0):
        self.txt = sshclient.read_until(self,until) 
        if not self.txt:
            if flag == 1:
                raise ValueError
            else :
                print("Connection to %s Closed Suddenly!!"%self.ap_ip)
                sys.exit()
    
    def execute(self,cmd,wait_until = "rkscli:"):
        self.read_the_output(wait_until)
        sshclient.write(self,cmd+"\n") 
    
    def check_whether_login_successful(self):
        self.read_the_output(flag = 1)
               
    def check_whether_download_successful(self):
        self.read_the_output()
        re.DOTALL
        result = re.search(r'.*CTL.*Get.*Error.*',self.txt)
        if result != None:
            print("Update failed!! Plese check your TEST_ENGINE_IPV4_ADDR and FIRMWARE FILE .....Error : CTL Get Error in %s"%self.ap_ip)
            sys.exit()
        else :
            pass

    def login(self):
        self.execute(self.username,wait_until = "Please login:")
        self.execute(self.password,wait_until = "password :")
        self.check_whether_login_successful()

    def download_image_via_tftp(self):
        sshclient.write(self,"fw set proto tftp\n")#usong write method directky becausse previous method already read the stdout
        self.execute("fw set host "+self.te_control_ip)
        self.execute("fw set control "+self.fw_name)
        self.execute("fw update")
        time.sleep(3)

    def reboot(self):
        self.execute("reboot")
        time.sleep(30)

    def logout(self):
        sshclient.close(self)
    
    def ping_the_ap(self):
        with open(os.devnull, 'w') as DEVNULL:
            try:
                subprocess.check_call(['ping','-c','1',self.ap_ip],stdout = DEVNULL,stderr = DEVNULL)
                is_up = True
            except subprocess.CalledProcessError:
                is_up = False
        return is_up

    def establish_ssh_to_ap(self,timeout = 600):
        i = 0
        base_time = time.time()
        while True :
            if self.ping_the_ap() == True:
                sshclient.__init__(self,self.ap_ip,username = self.username,password = self.password)
                self.login()
                break
            else:
                if time.time() - base_time > timeout:
                    print("UNABLE TO CONNECT TO THE %s AP!! PLEASE TRY AFTER SOMETIME"%self.ap_ip)
                    sys.exit()
                else:
                    continue
        
    def connect_to_ap(self):

        for password in range(1,4):  

            if self.Right_password:
                password = self.Right_password

            if password == 1 :
                self.username = os.environ['AP_LOGIN_USERNAME']
                self.password = os.environ['AP_LOGIN_PASSWORD']
            elif password == 2:
                self.username = os.environ['SCG_HOSTNAME']
                self.password = os.environ['SCG_HOSTNAME']
            elif password == 3:
                self.username = os.environ['AP_DEFAULT_USERNAME']
                self.password = os.environ['AP_DEFAULT_PASSWORD']
            try:
                self.establish_ssh_to_ap()#if connection is not successful it will through an exception

                #if connection is succesful next statements will execute
                self.Right_password = password #storing the right password for using to login second time Quickly
                break  #break from the loop if the connection is successful

            except ValueError:
                time.sleep(1)
                continue
        #if all of the credentials were wrong then else clause will execute        
        else:
            print("Unable to connect %s using any of the credentials"%self.ap_ip)
            sys.exit()

    def update_first_time(self):
        self.download_image_via_tftp()
        self.check_whether_download_successful()
        sshclient.write(self,"set rpmkey wsgclient/ignore-fw1\n")
        self.reboot()
        print("successfully updated first image of AP %s"%self.ap_ip)

    def update_second_time(self):
        self.download_image_via_tftp()
        self.check_whether_download_successful()
        sshclient.write(self,"set rpmkey wsgclient/ignore-fw1\n")
        print("successfully updated second image of AP %s"%self.ap_ip)

    def update(self):
        print("Please wait while firmware of AP %s is getting UPDATED"%self.ap_ip)
        self.connect_to_ap()
        self.update_first_time()
        self.connect_to_ap()
        self.update_second_time()
        self.logout()
        print("AP %s is SUCCESSFULLY UPDATED !!!"%self.ap_ip)

def main(FW_NAME,AP_IP):
    fw = FWUpdate(AP_IP,FW_NAME)
    fw.update()
   
if __name__ == "__main__":

    if len(sys.argv) < 3:
        print("incorrect USAGE!! The correct usage is as shown below.........\npython fw_update.py FIRMWARE_NAME AP1 [[AP2][AP3]....]")
        sys.exit()

    process = []   
    for i in range(2,len(sys.argv)):
        process.append(Process(target = main,args = (sys.argv[1],sys.argv[i])))
    for i in range(0,len(process)):
        process[i].start()
    for i in range(0,len(process)):    
        process[i].join()
