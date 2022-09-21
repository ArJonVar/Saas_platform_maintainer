#!/usr/bin/env python

import smartsheet, pandas as pd

class grid:

    """
    Global Variable
    ____________
    token --> MUST BE SET BEFORE PROCEEDING. >>> grid.token = {SMARTSHEET_ACCES_TOKEN}

    Dependencies
    ------------
    smartsheet as smart (smartsheet-python-sdk)
    pandas as pd

    Attributes
    __________
    grid_id: int
        sheet id of an existing Smartsheet sheet.

    Methods
    -------
    grid_id --> returns the grid_id
    grid_content ---> returns the content of a sheet as a dictionary.
    grid_columns ---> returns a list of the column names.
    grid_rows ---> returns a list of lists. each sub-list contains all the 'display values' of each cell in that row.
    grid_row_ids---> returns a list o
    f all the row ids
    grid_column_ids ---> returns a list of all the column ids
    df ---> returns a pandas DataFrame of the sheet.
    delete_all_rows ---> deletes all rows in the sheet (in preperation for updating).

    """

    token = None

    def __init__(self, grid_id):
        self.grid_id = grid_id
        self.grid_content = None
        self.column_df = self.get_column_df()
    
    def get_column_df(self):
        if self.token == None:
            return "MUST SET TOKEN"
        else:
            smart = smartsheet.Smartsheet(access_token=self.token)
            smart.errors_as_exceptions(True)
            return pd.DataFrame.from_dict(
            (smart.Sheets.get_columns(self.grid_id, level=2, include='objectValue', include_all=True)).to_dict().get("data")
        )

    def df_id_by_col(self, column_names):
        if self.token == None:
            return "MUST SET TOKEN"
        else:
            smart = smartsheet.Smartsheet(access_token=self.token)
            smart.errors_as_exceptions(True)
            columnids = []
            col_index = []
            for col in column_names:
                col1 = smart.Sheets.get_column_by_title(self.grid_id, col)
                columnids.append(col1.to_dict().get("id"))
                col_index.append(col1.to_dict().get("index"))
            sorted_col = [x for y, x in sorted(zip(col_index, column_names))]
            sfetch = smart.Sheets.get_sheet(self.grid_id, column_ids=columnids)
            cols = ["id"] + sorted_col
            c = []
            p = sfetch.to_dict()
            for i in p.get("rows"):
                l = []
                l.append(i.get("id"))
                for i in i.get("cells"):
                    l.append(i.get("displayValue"))
                c.append(l)
            return pd.DataFrame(c, columns=cols)

    def fetch_content(self):
        if self.token == None:
            return "MUST SET TOKEN"
        else:
            smart = smartsheet.Smartsheet(access_token=self.token)
            smart.errors_as_exceptions(True)
            self.grid_content = (smart.Sheets.get_sheet(self.grid_id)).to_dict()
            self.grid_name = (self.grid_content).get("name")
            # this attributes pulls the column headers
            self.grid_columns = [i.get("title") for i in (self.grid_content).get("columns")]
            # note that the grid_rows is equivelant to the cell's 'Display Value'
            self.grid_rows = []
            if (self.grid_content).get("rows") == None:
                self.grid_rows = []
            else:
                for i in (self.grid_content).get("rows"):
                    b = i.get("cells")
                    c = []
                    for i in b:
                        l = i.get("displayValue")
                        m = i.get("value")
                        if l == None:
                            c.append(m)
                        else:
                            c.append(l)
                    (self.grid_rows).append(c)
            self.grid_rows = self.grid_rows
            if (self.grid_content).get("rows") == None:
                self.grid_row_ids = []
            else:
                self.grid_row_ids = [i.get("id") for i in (self.grid_content).get("rows")]
            self.grid_column_ids = [i.get("id") for i in (self.grid_content).get("columns")]
            self.df = pd.DataFrame(self.grid_rows, columns=self.grid_columns)
            # if (self.grid_content).get('rows') == None:
            #     self.delete_all_rows = "no rows to delete"
            # else:
            #     self.delete_all_rows = smart.Sheets.delete_rows(self.grid_id, self.grid_row_ids)
            #     return "all rows deleted"
    def reduce_columns(self,exclusion_string):
        """a method on a grid{sheet_id}) object
        take in symbols/characters, reduces the columns in df that contain those symbols"""
        if self.token == None:
            return "MUST SET TOKEN"
        else:
            smart = smartsheet.Smartsheet(access_token=self.token)
            smart.errors_as_exceptions(True)
            regex_string = f'[{exclusion_string}]'
            self.column_reduction =  self.column_df[self.column_df['title'].str.contains(regex_string,regex=True)==False]
            self.reduced_column_ids = list(self.column_reduction.id)
            self.reduced_column_names = list(self.column_reduction.title)

# ######ARIEL######## #
    
    # def delete_empty_cells(self, reference_column_name):
    #     """must be done after fetch"""
    #     if self.token == None:
    #         return "MUST SET TOKEN"
    #     else:
    #         smart = smartsheet.Smartsheet(access_token=self.token)
    #         smart.errors_as_exceptions(True)
    #         # not sure how to do this grid/fetch content here
    #         empty_value_list = self.df.index[grid.df[reference_column_name].isnull()].tolist()
    #         empty_row_ids = [self.grid_row_ids[i] for i in empty_value_list ]

    #         try:
    #             smart.Sheets.delete_rows(
    #             self.grid_id,                       # sheet_id
    #             empty_row_ids)     # row_ids
                
    #         except:
    #             pass  

    # # didn't work
    # def values_per_key(self, value_key, row_id=None):
    #     if self.token == None:
    #         return "MUST SET TOKEN"
    #     else:
    #         smart = smartsheet.Smartsheet(access_token=self.token)
    #         smart.errors_as_exceptions(True)
    #         if row_id == None:
    #             full_data = smart.Sheets.get_sheet(self.grid_id, level='2', include='objectValue').to_dict()
    #         else:
    #             row_id = full_data = smart.Sheets.get_sheet(self.grid_id, row_ids=row_id, level='2', include='objectValue').to_dict()
    #         row_data = [i.get('cells') for i in full_data.get('rows')]
    #         values_per_key=[]
    #         for row_i in row_data:
    #             row_list = []
    #             for cell in row_i:
    #                 val = cell.get(value_key)
    #                 row_list.append(cell.get(value_key))
    #             values_per_key.append(row_list)
    #         return values_per_key


# ariel's notes:
#  if self.token == None:
#             return "MUST SET TOKEN"
#         else:
#             smart = smartsheet.Smartsheet(access_token=self.token)
#             smart.errors_as_exceptions(True)

# should be a verification funtion/instantiator in the class