# smartsheet grid class

## Language
Python >= 3.2

## Dependencies

- [Smartsheet Python SDK](https://pypi.org/project/smartsheet-python-sdk/) == 2.105.1
- [Pandas](https://pypi.org/project/pandas/)

## How-To

### Imports
```
from smartsheet_grid.smartsheet_grid import grid
```
### Set Smartsheet Access Token
```
grid.token = {SMARTSHEET-ACCESS-TOKEN}
```
### Create Object
```
grid_object = grid({SHEET_ID})
```
