from datetime import datetime

class ghetto_logger:
    def __init__(self, location):
        raw_now = datetime.now()
        self.now = raw_now.strftime("%d/%m/%Y %H:%M:%S")
        self.location=location
        self.first_use=True
        self.signature = f"\n{self.now} {location}   "
        self.dev_log_file="C:\Egnyte\Private\cobyvardy\Other_Projects\Python\Saas_platform_maintainer\deployment_logger.txt"
        self.server_log_file ="/Saas_platform_maintainer/saasadmin_av_logger.txt"

    def stamped_new_line(self, text, mode="a"):
        try:
            with open(self.dev_log_file, mode=mode) as file:
                file.write(self.signature + text)
        except:
            with open(self.dev_log_file, mode=mode) as file:
                file.write(self.signature + text)

    def new_line(self, text, mode="a"):
        try:
            with open(self.dev_log_file, mode=mode) as file:
                if self.first_use == True:
                    file.write(self.signature + text)
                    self.first_use = False
                elif self.first_use == False:
                    file.write("\n  " + text)
        except:
            with open(self.dev_log_file, mode=mode) as file:
                if self.first_use == True:
                    file.write(self.signature + text)
                    self.first_use = False
                elif self.first_use == False:
                    file.write("\n  " + text)

    def paragraph(self, text, mode="a"):
        try:
            with open(self.dev_log_file, mode=mode) as file:
                if self.first_use == True:
                    file.write(self.signature + text)
                    self.first_use = False
                elif self.first_use == False:
                    file.write(text)
        except:
            with open(self.dev_log_file, mode=mode) as file:
                if self.first_use == True:
                    file.write(self.signature + text)
                    self.first_use = False
                elif self.first_use == False:
                    file.write(text)