#region imports and variables
import sys
from turtle import update
import pandas as pd
import smartsheet
import numpy as np
import time
from datetime import datetime
from smartsheet.exceptions import ApiError
from smartsheet_grid.smartsheet_grid import grid
import requests
from requests.structures import CaseInsensitiveDict
import json
import re
import time
import pandas as pd

#endregion

class Saas_admin:
    '''This class creates and updates Smartsheet and Egnyte assets and links to project list'''
    def __init__(self, smartsheet_token, egnyte_token , dev_bool = False):
        raw_now = datetime.now()
        self.now = raw_now.strftime("%d/%m/%Y %H:%M:%S")
        self.dev_bool= dev_bool
        self.smartsheet_token = smartsheet_token
        self.egnyte_token = egnyte_token 
        grid.token=self.smartsheet_token
        self.smart = smartsheet.Smartsheet(access_token=self.smartsheet_token)
        self.smart.errors_as_exceptions(True)
        self.wkspc_template_id = 5301436075534212
        self.automated_wkspc_template_id = 7768425427691396
        self.saas_id = 5728420458981252 
        self.pl30_id= 3858046490306436
        self.field_admins_id = 2077914675079044
        self.project_admins_id= 2231803353294724
        self.project_review_id = 1394789389232004
        self.eg_template_path ='Shared/Projects/z_Templates/Project%20Folder%20Template' 
        self.ss_link = ""
        self.eg_link = "" 
#region helper funcs
    def try_except_pattern(self, value):
        '''wraps "value" in a try/accept format. used when pulling  info from DF because blank columns are not added to df, so you must try/except each df inquiry'''
        try:
            true_value = value
            if str(true_value) == "None":
                true_value = "none"
        except:
            true_value = "none"
        
        return true_value
    def regex_str_to_url(self, string):
        '''takes strings from query string (where %20 is a space) into normal english'''
        return re.sub(' ', '%20', string)
    @staticmethod
    def json_id_router(path, input_type=None, input=None, output_type=None):
        '''used to pull info from .json that lives in same folder as this code'''
        df = pd.read_json(path)
        try:
            return df.loc[df[input_type] == int(input)][output_type].values.tolist()[0]
        except:
            return df.loc[df[input_type] == input][output_type].values.tolist()[0]
    def json_router_handler(self, path, input_type=None, input=None, output_type=None):
        '''handles for errors via try/except'''
        try:
            retrieved_item = self.json_id_router(path, input_type, input, output_type)
            return retrieved_item
        except:
            return f"{input_type}: {input} did not yield a matching {output_type} item in {path}, check arguments of json_retriever_wrapper()"
#endregion
#region project data processing   
    def extract_enum_from_rowid(self, row_id):
        '''given a row_id on the saas sheet, returns enumerator. 
        Designed to allow a webhook on a row to trigger this script and start working with the project that is on that row'''
        saas_sheet = grid(self.saas_id)
        saas_sheet.fetch_content()
        saas_sheet.df['id'] = saas_sheet.grid_row_ids
        triggered_row = saas_sheet.df.loc[saas_sheet.df['id'] == int(row_id)]
        enum = triggered_row['ENUMERATOR'].values.tolist()[0]
        return enum
    def sheet_id_generator(self, enum):
        '''given an enumerator (project), finds the region and then sheet id of for that region's Regional Project List'''
        sheet = grid(self.pl30_id)
        sheet.fetch_content()
        proj_info_df = sheet.df.loc[sheet.df['ENUMERATOR'] == enum]
        region = proj_info_df['REGION'].values.tolist()[0]
        sheet_id = self.json_router_handler(path="pl3_regional_ids.json", input_type="region", input=region, output_type="sheetid")
        return sheet_id
    #region user processing 
    def process_permission_users(self, proj_info_df):
        '''makes the user list that holds employee full names.
        this list has been phased out due to issues with name changes, nick names, or incomplete usernames on saas apps'''
        pm = self.try_except_pattern(proj_info_df['PM'].values.tolist()[0])
        pe = self.try_except_pattern(proj_info_df['PE'].values.tolist()[0])
        sup = self.try_except_pattern(proj_info_df['SUP'].values.tolist()[0])
        fm = self.try_except_pattern(proj_info_df['FM'].values.tolist()[0])
        addtl_permission = self.try_except_pattern(proj_info_df["Platform Containers addt'l Permissions"].values.tolist()[0]).split(", ")
        requester = self.try_except_pattern(proj_info_df['NON SYS Created By'].values.tolist()[0])

        users = [pm, pe, sup, fm, requester]
        #integrate this list into the users list so its a single flat list
        if str(type(addtl_permission)) == "<class 'list'>":
            for name in addtl_permission:
                users.append(name)
        else:
            users.append(addtl_permission)

        # remove duplicates
        users = list(set(users))

        # remove names that start with _
        users = [name for name in users if not name.startswith("_")]

        # remove names that start with _
        users = [name for name in users if not name.startswith("future")]

        #remove excess "nones" if there is atleast one real value and a none to remove
        if len(users) != 1 and "none" in users:
            users.remove("none")

        return users    
    def filter_value_by_type(self, reduced_rows, json_key):
        '''filters a big .json holding sheet info from smartsheet given a specific key'''
        data_by_key=[]
        for row_i in reduced_rows:
            row_list = []
            for cell in row_i:
                row_list.append(cell.get(json_key))
            data_by_key.append(row_list)
        return data_by_key
    def grab_emails_from_data(self, df):
        '''isolates/grabs user emails from the dictionary that is posted on smartsheet in the Project List'''
        email_list = []
        for user in df.values.tolist()[0]:
            try:
                for user_value in user.get("values"):
                    email_list.append(user_value.get("email"))
            except:
                pass
        return email_list
    def process_permission_emails(self, sheet_id):
        '''function that does the work of getting the user emails. Makes a huge json, uses the other functions to extract specific columns and display Object Value, then creates the email list and returns it'''
        reduced_sheet = self.smart.Sheets.get_sheet(sheet_id, row_ids=self.row_id, column_ids = self.user_column_ids, level='2', include='objectValue').to_dict()
        reduced_rows = [i.get('cells') for i in reduced_sheet.get('rows')]
        val_df = pd.DataFrame(self.filter_value_by_type(reduced_rows, 'objectValue'), self.user_column_names)
        email_list = self.grab_emails_from_data(val_df)
        email_list_processed= [email for email in email_list if not('future' in email or 'tbd' in email)]
        if len(email_list_processed) == 0:
            # doesn't work with [] or ['None'] so my email is dummy
            return ['arielv@dowbuilt.com']
        else:
            return email_list_processed
    #endregion
    def value_from_saas_admin(self, enum, column_name):
        saas_sheet = grid(self.saas_id)
        saas_sheet.fetch_content()
        proj_info_df = saas_sheet.df.loc[saas_sheet.df['ENUMERATOR'] == enum]
        content = self.try_except_pattern(proj_info_df[column_name].values.tolist()[-1])

        return content
    def saas_bool_generator(self, link, enum, column_name):
        '''uses the saas sheet to check if someone requested assets. If they are not created and not requested, they will not go through'''
        try:
            num = self.value_from_saas_admin(enum, column_name)

            if str(link) == "none" and str(num) == "0":
                content = False
            else:
                content = True

        except:
            print("wasn't on saas_sheet")
            content = True

        return content
    def extract_projinfo_w_enum(self, sheet_id, enum):
        '''builds the proj_dict object that guides the action phase of this class'''
        sheet = grid(sheet_id)
        sheet.fetch_content()
        row_ids = sheet.grid_row_ids
        sheet.df["row_id"]=row_ids
        proj_info_df = sheet.df.loc[sheet.df['ENUMERATOR'] == enum]
        self.sheet_id =sheet_id
        self.debug = proj_info_df
        self.row_id= proj_info_df['row_id'].values.tolist()[0]
        self.user_column_names = ["Platform Containers addt'l Permissions", 'PM', 'PE', 'SUP', 'FM', 'NON SYS Created By']
        # Ben Rand wants full priv on all his projects!
        if proj_info_df["REGION"].values.tolist()[0] == 'HI':
            self.user_column_names.append("PRINCIPAL")
        self.user_column_ids= [sheet.column_df.loc[sheet.column_df['title'] == column]['id'].values.tolist()[0] for column in self.user_column_names]
        region = proj_info_df['REGION'].values.tolist()[0]
        name = proj_info_df['FULL NAME'].values.tolist()[0]
        enum = proj_info_df['ENUMERATOR'].values.tolist()[0]
        ss_link = self.try_except_pattern(proj_info_df['SMARTSHEET'].values.tolist()[0])
        eg_link = self.try_except_pattern(proj_info_df['EGNYTE'].values.tolist()[0])
        ss_bool = self.saas_bool_generator(ss_link, enum, 'SM Conditional')
        eg_bool = self.saas_bool_generator(eg_link, enum, 'EGN Conditional')
        update_bool = self.saas_bool_generator("none", enum, 'Update Done = CHECKED')
        action_type = self.value_from_saas_admin(enum, 'ADMINISTRATIVE Action Type')
        state = self.try_except_pattern(proj_info_df['STATE'].values.tolist()[0])
        users = self.process_permission_users(proj_info_df)
        user_emails = self.process_permission_emails(sheet_id)
        proj_dict = {'enum':enum, 'name': name, 'region':region, 'ss_link': ss_link, 'eg_link': eg_link, 'action_type':action_type, 'update_bool':update_bool, 'ss_bool': ss_bool, 'eg_bool': eg_bool, 'users':users, 'user_emails': user_emails, 'state':state}
        return proj_dict
    def check_finished_r_unrequested(self, proj_dict, str):
        if proj_dict.get(f"{str}_bool") == True and proj_dict.get(f"{str}_link") != "none":
            content = "finished"
        elif proj_dict.get(f"{str}_bool") == False and proj_dict.get(f"{str}_link") == "none":
            content = "unrequested"
        else:
            content = "requested"
        
        return content
    def audit_skips(self, proj_dict):
        if proj_dict.get('action_type').find("NEW") != -1:
            if self.check_finished_r_unrequested(proj_dict, "ss") != "requested" and self.check_finished_r_unrequested(proj_dict, "eg") != "requested":
                skip_bool = True
            else: 
                skip_bool = False
        elif proj_dict.get('action_type').find("UPDATE") != -1:
            if proj_dict.get('update_bool') == False:
                skip_bool = True
            else:
                skip_bool = False
        else:
            skip_bool = False
            print("Audit_skip did not find data it needed for audit")
        return skip_bool
#endregion
#region ss change components
    def get_ss_userlist(self):
        response = self.smart.Users.list_users(include_all=True)

        ss_user_list = []
        for item in response.data:
            email = item.to_dict().get("email")
            fname = self.try_except_pattern(item.to_dict().get("firstName"))
            lname = self.try_except_pattern(item.to_dict().get("lastName"))
            try:
                name = self.try_except_pattern(' '.join([fname, lname]))
            except:
                name = "none"

            ss_user_list.append({'email': email, "name": name})

        return ss_user_list
    def copy_template(self, name, enum):
        new_workspace = self.smart.Workspaces.copy_workspace(
        self.wkspc_template_id,           # workspace_id
        smartsheet.models.ContainerDestination({
            'new_name': f"Project_{name}_{enum}"
          })
        )

        return new_workspace.to_dict()
    def rename_wrkspc(self, wrkspc_id, name, enum):
        updated_workspace = self.smart.Workspaces.update_workspace(
         wrkspc_id,       # workspace_id
         smartsheet.models.Workspace({
           'name': f"Project_{name}_{enum}"
         })
        )

        return updated_workspace
    def find_wrkspc_id_from_enum(self, link):
        get_workspace_data = self.smart.Workspaces.list_workspaces(include_all=True).to_dict()
        workspace_list = get_workspace_data.get('data')
        id = "none"
        for wrkspc in workspace_list:
            if wrkspc.get("permalink") == link:
                id = wrkspc.get("id")
        
        return id
    def ss_permission_setting(self, wrkspc_id, proj_dict, user_list):

        # email_list = []
        # for user in proj_dict.get("users"):
        #     for user_profile in user_list:
        #         if user == user_profile.get("name"):
        #             email_list.append(user_profile.get("email"))
        email_list = proj_dict.get("user_emails")

        for email in email_list:
            try:
                response = self.smart.Workspaces.share_workspace(
                    wrkspc_id,       # workspace_id
                smartsheet.models.Share({
                  'access_level': 'ADMIN',
                  'email': email,
                })
                )
            except ApiError:
                print(f'{email} already have access to workspace')
        try:
            response = self.smart.Workspaces.share_workspace(
                wrkspc_id,
            smartsheet.models.Share({
              'access_level': 'ADMIN',
              'groupId': self.field_admins_id,
            })
            )
        except ApiError:
            print('field-admins already have access to workspace')
        try:
            response = self.smart.Workspaces.share_workspace(
                wrkspc_id,
            smartsheet.models.Share({
              'access_level': 'ADMIN',
              'groupId': self.project_admins_id,
            })
            )
        except ApiError:
            print('project-admins already have access to workspace')
        try:
            response = self.smart.Workspaces.share_workspace(
                wrkspc_id,
            smartsheet.models.Share({
              'access_level': 'EDITOR',
              'groupId': self.project_review_id,
            })
            )
        except ApiError:
            print('project-review already have access to workspace')
    def generate_ss_link(self, wrkspc_id):
        workspace = self.smart.Workspaces.get_workspace(wrkspc_id)
        link = workspace.to_dict().get("permalink")
        return link
    def audit_wrkspc_isnew(self):
        isnew_bool=True
        response = self.smart.Workspaces.list_workspaces(include_all=True)
        for workspace in response.to_dict().get("data"):
            if workspace.get("name") == f'Project_{self.proj_dict.get("name")}_{self.proj_dict.get("enum")}':
                isnew_bool = False
                print(f'a workspace audit within smartsheet revealed that Project_{self.proj_dict.get("name")}_{self.proj_dict.get("enum")} already exists')
        return isnew_bool
#endregion
#region eg change components
    
    #eg base funcs
    def generate_egnyte_access_token(self):
            url = "https://dowbuilt.egnyte.com/puboauth/token"
            headers = CaseInsensitiveDict()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            data = sensative_egnyte_instantiation 

            resp = requests.post(url, headers=headers, data=data)
            resp_dict = json.loads(resp.content.decode("utf-8"))
            self.egnyte_token = resp_dict.get("access_token")
    def generate_id_from_url(self, url):
            input = url
            split = re.split('https://dowbuilt.egnyte.com/navigate/folder/', input)
            return split[1]
    def generate_path_from_id(self, folder_id):
            
            url = f"https://dowbuilt.egnyte.com/pubapi/v1/fs/ids/folder/{folder_id}"
            headers = CaseInsensitiveDict()
            headers["Authorization"] = "Bearer fcqv9qnc2a7sk389xvuqp3cn"
            resp = requests.get(url, headers=headers)
            resp_dict = json.loads(resp.content.decode("utf-8"))
            folder_information_pretty = json.dumps(resp_dict, indent=4)
            folder_information_dict = json.loads(folder_information_pretty)

            return folder_information_dict.get("path")
    def generate_api_url(self, path, type):
            if type == "folder update":
                api_url = 'https://dowbuilt.egnyte.com/pubapi/v1/fs'
            if type == "get permissions":
                api_url = 'https://dowbuilt.egnyte.com/pubapi/v2/perms'
            # Changing spaces back to %20
            url_path = re.sub("\s", "%20", path)
            full_api_url = api_url + url_path
            return full_api_url
    
    #folder api (new & update)
    def oldpath_to_newpath(self, path, new_name):
            split_slash = re.split("/", path)
            position_of_old_name=len(split_slash)-1
            old_name = split_slash[position_of_old_name]
            final_path = re.sub(old_name, new_name, path)
            # print('final path', final_path)
            return final_path
    def change_folder_name(self, url, path):
            headers = CaseInsensitiveDict()
            headers["Authorization"] = f"Bearer {self.egnyte_token}"
            headers["Content-Type"] = "application/json"

            data = '{"action":"move", "destination":"' + f"{path}" + '"}'

            resp = requests.post(url, headers=headers, data=data)
    def create_folder(self, path):
        url=f'https://dowbuilt.egnyte.com/pubapi/v1/fs/{path}'
        
        headers = CaseInsensitiveDict()
        headers["Authorization"] = f"Bearer {self.egnyte_token}"
        headers["Content-Type"] = "application/json"

        data = '{"action":"add_folder"}'

        resp = requests.post(url, headers=headers, data=data)
    def copy_template_to_new_folder(self, destination_path):
        url = f"https://dowbuilt.egnyte.com/pubapi/v1/fs/{self.eg_template_path}"

        headers = CaseInsensitiveDict()
        headers["Authorization"] = f"Bearer {self.egnyte_token}"
        headers["Content-Type"] = "application/json"

        data = '{"action":"copy", "destination":"' + destination_path + '", "permissions": "inherit_from_parent"}'


        resp = requests.post(url, headers=headers, data=data)
    def restrict_move_n_delete(self, path):
        url = f"https://dowbuilt.egnyte.com/pubapi/v1/fs/{path}"

        headers = CaseInsensitiveDict()
        headers["Authorization"] = f"Bearer {self.egnyte_token}"
        headers["Content-Type"] = "application/json"        

        data = '{"restrict_move_delete": "true"}'       

        resp = requests.patch(url, headers=headers, data=data)
    def generate_folder_link(self, path):
        url = f"https://dowbuilt.egnyte.com/pubapi/v1/fs/{path}"

        headers = CaseInsensitiveDict()
        headers["Authorization"] = f"Bearer {self.egnyte_token}"


        resp = requests.get(url, headers=headers)
        resp_dict = json.loads(resp.content.decode("utf-8"))
        information_pretty = json.dumps(resp_dict, indent=4)
        information_dict = json.loads(information_pretty)   
        id = information_dict.get("folder_id")
        link = 'https://dowbuilt.egnyte.com/navigate/folder/' + id
        return link
    
    #eg permission group list
    def eg_user_list_api_call(self, index, eg_user_list):
        recursion_bool = True

        url = f"https://dowbuilt.egnyte.com/pubapi/v2/users?count=100&startIndex={index}"
        headers = CaseInsensitiveDict()
        headers["Authorization"] = f"Bearer {self.egnyte_token}"

        resp = requests.get(url, headers=headers)
        resp_dict = json.loads(resp.content.decode("utf-8"))
        information_pretty = json.dumps(resp_dict, indent=4)
        information_dict = json.loads(information_pretty)

        for user in information_dict.get("resources"):
            name = user.get("name"). get("formatted")
            user_id = user.get("id")
            email = user.get("email")
            eg_user_dict = {"name": name, "email": email, "id": user_id}
            eg_user_list.append(eg_user_dict)
        if len(information_dict.get("resources")) == 0:
            recursion_bool = False

        return recursion_bool
    def recusively_generate_eg_user_list(self, index, eg_user_list):
        recursion_bool = self.eg_user_list_api_call(index, eg_user_list)
        # print('index: ', index, " length: ", len(eg_user_list))
        if recursion_bool == True:
            new_index = int(index) + 100
            self.recusively_generate_eg_user_list(new_index, eg_user_list)

        return eg_user_list

    #update permission group names
    def url_to_permission_report(self, url):
            # print(url, 'start')
            try:
                headers = CaseInsensitiveDict()
                headers["Authorization"] = f"Bearer {self.egnyte_token}"

                resp = requests.get(url, headers=headers)
                report_dict = json.loads(resp.content.decode("utf-8"))
                return report_dict
            except:
                print("url did not yield folder that existed")
    def permission_report_to_full(self, report):
            permission_list = []
            try:
                for group, permissions_state in report.get('groupPerms').items():
                    if permissions_state == "Full":
                        permission_list.append(group)
                        # full_permission_group = group
                for item in permission_list:
                    if item.find("State") == 0:
                        permission_list.remove(item)
                    if item.find("Projects") == 0:
                        permission_list.remove(item)
                return permission_list[0]
            except:
                print("no group has full permissions in this folder")
    def find_id_from_group_name(self, group_name):
            url_group_name = re.sub("\s", "%20", group_name)
            url = 'https://dowbuilt.egnyte.com/pubapi/v2/groups?filter=displayName%20eq%20"' + f"{url_group_name}" + '"'
            headers = CaseInsensitiveDict()
            headers["Authorization"] = f"Bearer {self.egnyte_token}"

            resp = requests.get(url, headers=headers)
            resp_dict = json.loads(resp.content.decode("utf-8"))
            id = resp_dict.get("resources")[0].get("id")
            return id
    def change_permission_group_name(self, new_name):
            url = 'https://dowbuilt.egnyte.com/pubapi/v2/groups/' + f"{self.permission_group_id}" 
            headers = CaseInsensitiveDict()
            headers["Authorization"] = f"Bearer {self.egnyte_token}"
            headers["Content-Type"] = "application/json"

            data = '{"displayName": "' + f"{new_name}" '"}'
            resp = requests.patch(url, headers=headers, data=data)
    
    #update permission group members
    def get_permission_group_members(self):
        url = f"https://dowbuilt.egnyte.com/pubapi/v2/groups/{self.permission_group_id}"

        headers = CaseInsensitiveDict()
        headers["Authorization"] = f"Bearer {self.egnyte_token}"


        resp = requests.get(url, headers=headers)
        resp_dict = json.loads(resp.content.decode("utf-8"))
        information_pretty = json.dumps(resp_dict, indent=4)
        permission_members_obj = json.loads(information_pretty)

        return permission_members_obj
    def identify_permission_updates(self, permission_members_obj):
        users_in_group = []
        for user in permission_members_obj.get("members"):
            users_in_group.append(user.get("value"))

        user_updates_list = []
        for user in self.proj_dict.get("user_emails"):
            for account in self.eg_user_list:
                if user == account.get("email"):
                    id = account.get("id")
            if id not in users_in_group:
                user_updates_list.append(user)

        return user_updates_list
    def update_permission_group_members_manager(self, user_updates_list):
        for user in user_updates_list:
            for user_data in self.eg_user_list:
                if user == user_data.get("email"):
                    print("adding ", user_data.get("name"), " to permission group")
                    self.update_permission_group_members(user_data.get("id"))
    def update_permission_group_members(self,user_data):
        url = f"https://dowbuilt.egnyte.com/pubapi/v2/groups/{self.permission_group_id}"

        headers = CaseInsensitiveDict()
        headers["Authorization"] = f"Bearer {self.egnyte_token}"
        headers["Content-Type"] = "application/json"

        data = '{"members":[{"value":'+ str(user_data) + '}]}'


        resp = requests.patch(url, headers=headers, data=data)
    
    #new permission group
    def prepare_new_permission_group(self):
        permission_members = []
        for employee in self.proj_dict.get("user_emails"):
            if employee == "none":
                pass
            else:
                for user in self.eg_user_list:
                    if employee == user.get("email"):
                        permission_members.append({"value":user.get("id")})
        return permission_members
    def generate_permission_group(self, permission_members):
        url = "https://dowbuilt.egnyte.com/pubapi/v2/groups"

        headers = CaseInsensitiveDict()
        headers["Authorization"] = f"Bearer {self.egnyte_token}"
        headers["Content-Type"] = "application/json"

        if len(permission_members) == 0:
            data_raw='{"displayName":"' +  self.proj_dict.get("name")+"_"+self.proj_dict.get("enum") + '}'
        else:
            data_raw = '{"displayName":"' +  self.proj_dict.get("name")+"_"+self.proj_dict.get("enum")  +'", "members":' + str(permission_members) + '}'
            data = re.sub("\'", '"', data_raw)

        resp = requests.post(url, headers=headers, data=data)
        resp_dict = json.loads(resp.content.decode("utf-8"))
        information_pretty = json.dumps(resp_dict, indent=4)
        information_dict = json.loads(information_pretty)
        return information_dict.get("id")
    def set_permission_on_new_folder(self, path):
        url = f"https://dowbuilt.egnyte.com/pubapi/v2/perms/{path}"
        headers = CaseInsensitiveDict()
        headers["Authorization"] = f"Bearer {self.egnyte_token}"
        headers["Content-Type"] = "application/json"
        if self.proj_dict.get('state') != "CA":
            state = self.proj_dict.get('state')
        elif self.proj_dict.get('region') == "NORCAL":
            state = 'NorCal'
        elif self.proj_dict.get('region') == "SOCAL":
            state = 'SoCal'
        data = '{"groupPerms":{"' + f"{self.proj_dict.get('name')}_{self.proj_dict.get('enum')}" + '":"Full", "State_' + state + '":"Editor", "Projects": "Editor"}}'
        resp = requests.post(url, headers=headers, data=data)


#endregion
#region ss post
    def get_post_ids(self):
        '''uses the regional sheet id to gather column ids for Egnyte and Smartsheet column and row Id for row with the enum we are working with'''
        sheet = grid(self.sheet_id)
        sheet.fetch_content()
        sheet_columns = sheet.get_column_df()
        row_ids = sheet.grid_row_ids
        sheet.df["id"]=row_ids

        eg_column_id = sheet_columns.loc[sheet_columns['title'] == "EGNYTE"]["id"].tolist()[0]
        ss_column_id = sheet_columns.loc[sheet_columns['title'] == "SMARTSHEET"]["id"].tolist()[0]
        row_id = sheet.df.loc[sheet.df['ENUMERATOR'] == self.proj_dict.get("enum")]["id"].tolist()[0]
        posting_data = {"eg" : eg_column_id, "ss" : ss_column_id, "row": row_id}

        return posting_data
    def post_resulting_links(self, posting_data):
        new_row = self.smart.models.Row()
        new_row.id = posting_data.get("row")

        link_list = [{'column_id': posting_data.get("eg"), 'link': self.eg_link}, {'column_id': posting_data.get("ss"), 'link': self.ss_link}]
        for item in link_list:
            if item.get("link") != "":
                new_cell = self.smart.models.Cell()
                new_cell.column_id = item.get("column_id")
                new_cell.value = item.get("link")
                new_cell.strict = False

                # Build the row to update
                new_row.cells.append(new_cell)
        if str(new_row.to_dict().get("cells")) != "None":
            # Update rows
            updated_row = self.smart.Sheets.update_rows(
              self.sheet_id,      # sheet_id
              [new_row])
            print(f'link-post into {self.proj_dict.get("region")} Project List complete')
    def generate_update_post_data(self):
        '''uses the regional sheet id to gather column ids for Egnyte and Smartsheet column and row Id for row with the enum we are working with'''
        sheet = grid(self.saas_id)
        sheet.fetch_content()
        sheet_columns = sheet.get_column_df()
        row_ids = sheet.grid_row_ids
        sheet.df["id"]=row_ids
        update_bool_column_id = sheet_columns.loc[sheet_columns['title'] == "Update Done = CHECKED"]["id"].tolist()[0]
        # returns all rows that have updated this enum
        rows = sheet.df.loc[sheet.df['ENUMERATOR'] == self.proj_dict.get("enum")]["id"].tolist()
        #IF A CHECK DOES NOT WORK ITS B/C OF THIS!! ([0]) #problem #search #find
        row_id = rows[len(rows)-1]
        posting_data = {"update_col_id" : update_bool_column_id,"row": row_id}

        return posting_data
    def post_update(self, posting_data):
        new_cell = self.smart.models.Cell({'column_id' : posting_data.get("update_col_id"), 'value': "1", 'strict': False})
        new_row = self.smart.models.Row({'id':posting_data.get("row")})
        new_row.cells.append(new_cell)

        # data={'id':post.ing_data.get("row"), 'column_id':posting_data.get("update_col_id"), 'value':'1', "strict":False}
        # print(data)

        if str(new_row.to_dict().get("cells")) != "None":
            # Update rows
            updated_row = self.smart.Sheets.update_rows(
              self.saas_id,      # sheet_id
              [new_row])
            print('post had result of: ', updated_row.message)
            print(f'checked update bool in Saas Admin Page')
#endregion
#region cron job prep
    def get_row_array(self):
        '''gets array of row ids that have open saas status in saas intake form'''
        sheet = grid(self.saas_id)
        sheet.fetch_content()
        sheet_columns = sheet.get_column_df()
        row_ids = sheet.grid_row_ids
        sheet.df["id"]=row_ids
        row_id_array = sheet.df.loc[sheet.df['Saas Status'] == "Open"]['id'].tolist()
        return row_id_array
#endregion
#region change decisions
    def ss_new(self):
        print(f"Creating Smartsheet Workspace for {self.proj_dict.get('name')}")
        new_wrkspc =  self.copy_template(self.proj_dict.get("name"), self.enum)
        self.wrkspc_id = new_wrkspc.get("data").get("id")
        self.ss_permission_setting(self.wrkspc_id, self.proj_dict, self.ss_user_list)
        self.ss_link = self.generate_ss_link(self.wrkspc_id)
        print("ss creation complete")
    def ss_update(self):           
        print(f"Updating Smartsheet Workspace for {self.proj_dict.get('name')}")
        self.wrkspc_id =  self.find_wrkspc_id_from_enum(self.proj_dict.get("ss_link"))
        self.rename_wrkspc(self.wrkspc_id, self.proj_dict.get("name"), self.enum)
        self.ss_permission_setting(self.wrkspc_id, self.proj_dict, self.ss_user_list)
        
        #update saas admin
        self.post_update(self.generate_update_post_data())
        print("ss update complete")
    def eg_new(self):
        print(f"Creating Egnyte Folder for {self.proj_dict.get('name')}")
        if self.proj_dict.get('state') != "CA":
            path = f"Shared/Projects/{self.proj_dict.get('state')}/{self.proj_dict.get('name')}_{self.proj_dict.get('enum')}"
        elif self.proj_dict.get('region') == "NORCAL":
            path = f"Shared/Projects/NorCal/{self.proj_dict.get('name')}_{self.proj_dict.get('enum')}"
        elif self.proj_dict.get('region') == "SOCAL":
            path = f"Shared/Projects/SoCal/{self.proj_dict.get('name')}_{self.proj_dict.get('enum')}"  
        self.create_folder(path)
        permission_group = self.prepare_new_permission_group()
        self.permission_group_id = self.generate_permission_group(permission_group)
        self.set_permission_on_new_folder(path)
        self.copy_template_to_new_folder(path)
        self.restrict_move_n_delete(path)
        self.eg_link = self.generate_folder_link(path)
        print('eg creation complete')
    def eg_update(self):
        asset_name = self.proj_dict.get('name') + "_" + self.proj_dict.get('enum')
        print(f"updating Egnyte for {asset_name}")
        print("sleeping for 5 sec...")
        time.sleep(5)
        folder_id = self.generate_id_from_url(self.proj_dict.get("eg_link"))
        self.path = self.generate_path_from_id(folder_id)
        
        #update permission group
        print("sleeping for 10 sec...")
        time.sleep(5)
        print("half way done sleeping")
        time.sleep(5)
        self.permissions_url=self.generate_api_url(self.path, "get permissions")
        self.report=self.url_to_permission_report(self.permissions_url)
        self.full_permission_group = self.permission_report_to_full(self.report)
        self.permission_group_id = self.find_id_from_group_name(self.full_permission_group)
        self.permission_members_obj = self.get_permission_group_members()
        self.user_updates_list = self.identify_permission_updates(self.permission_members_obj)
        self.update_permission_group_members_manager(self.user_updates_list)
        self.change_permission_group_name(asset_name)
        
        #update folder
        self.new_path=self.oldpath_to_newpath(self.path, asset_name)
        self.update_url=self.generate_api_url(self.path, "folder update")
        self.change_folder_name(self.update_url, self.new_path)
        self.restrict_move_n_delete(self.new_path)

        #update saas admin
        self.post_update(self.generate_update_post_data())
        print('eg update complete')
    def execute_link_post(self):
        posting_data = self.get_post_ids()
        self.post_resulting_links(posting_data)

#endregion
#region run
    def run_eg(self, link, bool):
        self.eg_user_list = self.recusively_generate_eg_user_list(1, [])
        
        if link == "none" and bool == True:
            # pass
            self.eg_new()

        elif self.proj_dict.get("eg_link") != "none": 
            # pass
            self.eg_update()
    def run_ss(self, link, bool):
        self.ss_user_list = self.get_ss_userlist()
        isnew_bool = self.audit_wrkspc_isnew()
         
        if link == "none" and bool == True and isnew_bool==True:
            self.ss_new()

        elif self.proj_dict.get("ss_link") != "none":
            # pass
            self.ss_update()
    def run_print_statements(self, dict):
        print(f'''
                            {dict.get('name')} PROJECT DATA:  
                            
enum: {dict.get('enum')}, name: {dict.get('name')}
region: {dict.get('region')}, state: {dict.get('state')}
user: {dict.get('user')}, user_emails: {dict.get('user_emails')}
action_type: {dict.get('action_type')}, update_bool:{dict.get('update_bool')},
eg_bool: {dict.get('eg_bool')}, ss_bool: {dict.get('ss_bool')}
eg_link: {dict.get('eg_link')}
ss_link: {dict.get('ss_link')}

''')
    def run(self, data):
        '''main f(x), data is assumed to be enumerator unless it is long, then assumed to be row id from Saas Intake Forms (https://app.smartsheet.com/sheets/4X2m4ChQjgGh2gf2Hg475945rwVpV5Phmw69Gp61?view=grid)
        the function gathers a dictionary of project info (name/region/users who need access/links)
        then  runs through egnyte and ss run protocol'''
        self.enum=data
        if len(data) > 7:
            #data will row_id, which would happen if this was triggered via webhook
            self.enum = self.extract_enum_from_rowid(data)
        self.sheet_id = self.sheet_id_generator(self.enum)
        self.proj_dict = self.extract_projinfo_w_enum(self.sheet_id, self.enum)
        self.run_print_statements(self.proj_dict)
        if self.audit_skips(self.proj_dict) == True:
            print(f"{self.proj_dict.get('name')} skipped b/c already updated")
        else:
            self.run_ss(self.proj_dict.get("ss_link"), self.proj_dict.get("ss_bool"))
            self.run_eg(self.proj_dict.get("eg_link"), self.proj_dict.get("eg_bool"))
            self.execute_link_post()
            if self.proj_dict.get('ss_link') == "none" and self.proj_dict.get('eg_link') == "none" and str(self.proj_dict.get('ss_bool')) == "False" and str(self.proj_dict.get('eg_bool')) == "False" :
                # if there is absolutely nothing to do, just post that it was updated in check box
                self.post_update(self.generate_update_post_data())
            print(f"fineeto w/ {self.proj_dict.get('name')}")
    def cron_run(self):
        array = self.get_row_array()
        for id in array:
            try:
                self.run(str(id))
                print("15 sec sleep between updates")
                time.sleep(5)
            except:
                pass
        print("Cron Finished")
    def partial_run(self, data):
        '''main f(x), data is assumed to be enumerator unless it is long, then assumed to be row id from Saas Intake Forms (https://app.smartsheet.com/sheets/4X2m4ChQjgGh2gf2Hg475945rwVpV5Phmw69Gp61?view=grid)
        the function gathers a dictionary of project info (name/region/users who need access/links)
        '''
        self.enum=data
        if len(data) > 7:
            #data will row_id, which would happen if this was triggered via webhook
            self.enum = self.extract_enum_from_rowid(data)
        self.sheet_id = self.sheet_id_generator(self.enum)
        self.proj_dict = self.extract_projinfo_w_enum(self.sheet_id, self.enum)
        self.run_print_statements(self.proj_dict)
        if self.audit_skips(self.proj_dict) == True:
            print(f"{self.proj_dict.get('name')} skipped b/c already updated")
        print(f"fineeto w/ {self.proj_dict.get('name')}")
#endregion
    def useless(self):
        '''exists to make the other regions close nicely (the final region on a page cannot be closed if nothing is below it)'''
        pass


#region run
if __name__ == "__main__":
    sa = Saas_admin("smartsheet_token", "egnyte_token")
    # for cron run:
    sa.cron_run()
    # for individual run:
    sa.run("data")
#endregion