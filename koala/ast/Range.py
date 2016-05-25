import re
import string
from ExcelError import ExcelError
from excelutils import *

# WARNING: Range should never be imported directly. Import Range from excelutils instead.

### Range Utils ###

CELL_REF_RE = re.compile(r"\!?(\$?[A-Za-z]{1,3})(\$?[1-9][0-9]{0,6})$")

cache = {}

def parse_cell_address(ref):
    try:
        if ref not in cache:
            found = re.search(CELL_REF_RE, ref)
            col = found.group(1)
            row = found.group(2)
            result = (int(row), col)
            cache[ref] = result
            return result
        else:
            return cache[ref]
    except:
        raise Exception('Couldn\'t find match in cell ref')
    
def get_cell_address(sheet, tuple):
    row = tuple[0]
    col = tuple[1]

    if sheet is not None:
        return sheet + '!' + col + str(row)
    else:
        return col + str(row)

def check_value(a):
    try: # This is to avoid None or Exception returned by Range operations
        if float(a):
            if type(a) == float:
                return round(a, 10)
            else:
                return a
        else:
            return 0
    except:
        return 0


class RangeCore(dict):

    def __init__(self, address, values = None, cellmap = None, nrows = None, ncols = None, name = None):
        
        if type(address) == list: # some Range calculations such as excellib.countifs() use filtered keys
            cells = address
        else:
            address = address.replace('$','')
            try:
                cells, nrows, ncols = resolve_range(address)
            except:
                raise ValueError('Range must not be a scalar')

        cells = list(flatten(cells))

        if cellmap:
            cells = [cell for cell in cells if cell in cellmap]

        # if len(cells) > 0 and cells[0] == cells[len(cells) - 1]:
        #     print 'WARNING Range is a scalar', address, cells

        # Fill the Range with cellmap values 
        # if cellmap:
        #     cells = [cell for cell in cells if cell in cellmap]

        #     values = []

        #     for cell in cells:
        #         if cell in cellmap: # this is to avoid Sheet1!A5 and other empty cells due to A:A style named range
        #             try:
        #                 if isinstance(cellmap[cell].value, RangeCore):
        #                     raise Exception('Range can\'t be values of Range')
        #                 values.append(cellmap[cell].value)
        #             except: # if cellmap is not filled with actual Cells (for tests for instance)
        #                 if isinstance(cellmap[cell], RangeCore):
        #                     raise Exception('Range can\'t be values of Range')
        #                 values.append(cellmap[cell])

        if values:
            if len(cells) != len(values):
                raise ValueError("cells and values in a Range must have the same size")

        try:
            sheet = cells[0].split('!')[0]
        except:
            sheet = None

        result = []
        order = []

        for cell, value in zip(cells, values):
            row,col = parse_cell_address(cell)
            order.append((row, col))
            try:
                if cellmap:
                    result.append(((row, col), cellmap[cell]))

                else:
                    if isinstance(values[index], RangeCore):
                        raise Exception('Range can\'t be values of Range', address)
                    result.append(((row, col), values[index]))

            except: # when you don't provide any values
                result.append(((row, col), None))

        # dont allow messing with these params
        self.__cellmap = cellmap
        self.__address = address
        self.__name = address if type(address) != list else name
        self.__cells = cells
        self.order = order
        self.__length = len(cells)
        self.__nrows = nrows
        self.__ncols = ncols
        if ncols == 1 and nrows == 1:
            self.__type = 'scalar'
        elif ncols == 1:
            self.__type = 'vertical'
        elif nrows == 1:
            self.__type = 'horizontal'
        else:
            self.__type = 'bidimensional'
        self.__sheet = sheet
        self.__start = parse_cell_address(cells[0]) if len(cells) > 0 else None

        self.need_update = False

        dict.__init__(self, result)


    @property
    def address(self):
        return self.__address
    @property
    def name(self):
        return self.__name
    @property
    def cells(self):
        return self.__cells
    @property
    def length(self):
        return self.__length
    @property
    def nrows(self):
        return self.__nrows
    @property
    def ncols(self):
        return self.__ncols
    @property
    def type(self):
        return self.__type
    @property
    def sheet(self):
        return self.__sheet
    @property
    def start(self):
        return self.__start
    @property
    def value(self):
        if self.__cellmap:
            values = []
            for cell in self.cells:
                values.append(self.__cellmap[cell].value)
            return values
        else:
            return self.values()
    
    @value.setter
    def value(self, new_values):
        # for index, key in enumerate(self.keys()):
            # self[key] = new_values[index]
        if self.__cellmap:
            for index, cell in enumerate(self.values()):
                cell.value = new_values[index]
        else:
            for key, value in enumerate(self.keys()):
                self[value] = new_values[key]


    def values(self):
        return map(lambda c: self[c], self.order)

    def reset(self, addr):
        self.need_update = True
        
        if addr is not None:
            if addr == "Calculations!P91":
                print 'resetting', addr
            self[parse_cell_address(addr)].need_update = True
            self[parse_cell_address(addr)].value = None
        else:
            for cell in self.values():
                cell.value = None

    # def is_associated(self, other):
    #     if self.length != other.length:
    #         return None

    #     nb_v = 0
    #     nb_c = 0

    #     for index, key in enumerate(self.keys()):
    #         r1, c1 = key
    #         r2, c2 = other.keys()[index]

    #         if r1 == r2:
    #             nb_v += 1
    #         if c1 == c2:
    #             nb_c += 1

    #     if nb_v == self.length:
    #         return 'v'
    #     elif nb_c == self.length:
    #         return 'c'
    #     else:
    #         return None

    def get(self, row, col = None):
        nr = self.nrows
        nc = self.ncols

        values = self.value
        cells = self.cells

        if nr == 1 or nc == 1: # 1-dim range
            if col is not None:
                raise Exception('Trying to access 1-dim range value with 2 coordinates')
            else:
                return values[row - 1]
            
        else: # could be optimised
            indices = range(len(values))

            if row == 0: # get column
                filtered_indices = filter(lambda x: x % nc == col - 1, indices)

                filtered_values = map(lambda i: values[i], filtered_indices)
                filtered_cells = map(lambda i: cells[i], filtered_indices)

                new_address = str(filtered_cells[0]) + ':' + str(filtered_cells[len(filtered_cells)-1])

                return RangeCore(new_address, filtered_values)

            elif col == 0: # get row

                filtered_indices = filter(lambda x: (x / nc) == row - 1, indices)

                filtered_values = map(lambda i: values[i], filtered_indices)
                filtered_cells = map(lambda i: cells[i], filtered_indices)

                new_address = str(filtered_cells[0]) + ':' + str(filtered_cells[len(filtered_cells)-1])

                return RangeCore(new_address, filtered_values)

            else:
                base_col_number = col2num(cells[0][0])
                new_ref = num2col(col + base_col_number - 1) + str(row)
                new_value = values[(row - 1)* nc + (col - 1)]

                return new_value

    @staticmethod
    def find_associated_values(ref, first = None, second = None):
        row, col = ref

        if isinstance(first, RangeCore):
            try:
                if (first.length) == 0: # if a Range is empty, it means normally that all its cells are empty
                    first_value = 0
                elif first.type == "vertical":
                    if first.__cellmap is not None:
                        first_value = first[(row, first.start[1])].value
                    else:
                        first_value = first[(row, first.start[1])]
                elif first.type == "horizontal":
                    if first.__cellmap is not None:
                        try:
                            first_value = first[(first.start[0], col)].value
                        except:
                            print 'WHAT', first[(first.start[0], col)]
                            raise Exception
                    else:
                        first_value = first[(first.start[0], col)]
                else:
                    raise ExcelError('#VALUE!', 'cannot use find_associated_values on %s' % first.type)
            except ExcelError as e:
                raise Exception('First argument of Range operation is not valid: ' + e)
        else:
            first_value = first


        if isinstance(second, RangeCore):
            try:
                if (second.length) == 0: # if a Range is empty, it means normally that all its cells are empty
                    second_value = 0
                elif second.type == "vertical":
                    if second.__cellmap is not None:
                        second_value = second[(row, second.start[1])].value
                    else:
                        second_value = second[(row, second.start[1])]
                elif second.type == "horizontal":
                    if second.__cellmap is not None:
                        second_value = second[(second.start[0], col)].value
                    else:
                        second_value = second[(second.start[0], col)]
                else:
                    raise ExcelError('#VALUE!', 'cannot use find_associated_values on %s' % second.type)

            except ExcelError as e:
                raise Exception('Second argument of Range operation is not valid: ' + e)
        else:
            second_value = second
        
        return (first_value, second_value)

    @staticmethod
    def apply_one(func, self, other, ref = None):
        function = func_dict[func]

        if ref is None:
            first = self
            second = other
        else:
            first, second = RangeCore.find_associated_values(ref, self, other)

        return function(first, second)

    @staticmethod
    def apply_all(func, self, other, ref = None):
        function = func_dict[func]

        # Here, the first arg of RangeCore() has little importance: TBC
        if isinstance(self, RangeCore) and isinstance(other, RangeCore):
            if self.length != other.length:
                raise ExcelError('#VALUE!', 'apply_all must have 2 Ranges of identical length')
            vals = [function(x.value if type(x) == Cell else x, y if type(y) == Cell else y) for x,y in zip(self.values(), other.values())]
            return RangeCore(self.cells, vals, nrows = self.nrows, ncols = self.ncols)
        elif isinstance(self, RangeCore):
            vals = [function(x.value if type(x) == Cell else x, other) for x in self.values()]
            return RangeCore(self.cells, vals, nrows = self.nrows, ncols = self.ncols)
        elif isinstance(other, RangeCore):
            vals = [function(self, x.value if type(x) == Cell else x) for x in other.values()]
            return RangeCore(other.cells, vals, nrows = other.nrows, ncols = other.ncols)
        else:
            return function(self, other)


    @staticmethod
    def add(a, b):
        try:
            return check_value(a) + check_value(b)
        except Exception as e:
            return ExcelError('#N/A', e)

    @staticmethod
    def substract(a, b):
        try:
            return check_value(a) - check_value(b)
        except Exception as e:
            return ExcelError('#N/A', e)

    @staticmethod
    def minus(a, b = None):
        # b is not used, but needed in the signature. Maybe could be better
        try:
            return -check_value(a)
        except Exception as e:
            return ExcelError('#N/A', e)


    @staticmethod
    def multiply(a, b):
        try:
            return check_value(a) * check_value(b)
        except Exception as e:
            return ExcelError('#N/A', e)

    @staticmethod
    def divide(a, b):
        try:
            return float(check_value(a)) / float(check_value(b))
        except Exception as e:
            return ExcelError('#N/A', e)

    @staticmethod
    def is_equal(a, b):
        try:            
            if type(a) != str:
                a = check_value(a)
            if type(b) != str:
                b = check_value(b)
            # if a == 'David':
            #     print 'Check value', check_value(a)


            return a == b
        except Exception as e:
            return ExcelError('#N/A', e)

    @staticmethod
    def is_not_equal(a, b):
        try:
            if type(a) != str:
                a = check_value(a)
            if type(b) != str:
                b = check_value(b)

            return a != b
        except Exception as e:
            return ExcelError('#N/A', e)

    @staticmethod
    def is_strictly_superior(a, b):
        try:
            return check_value(a) > check_value(b)
        except Exception as e:
            return ExcelError('#N/A', e)

    @staticmethod
    def is_strictly_inferior(a, b):
        try:
            return check_value(a) < check_value(b)
        except Exception as e:
            return ExcelError('#N/A', e)

    @staticmethod
    def is_superior_or_equal(a, b):
        try:
            return check_value(a) >= check_value(b)
        except Exception as e:
            return ExcelError('#N/A', e)

    @staticmethod
    def is_inferior_or_equal(a, b):
        try:
            return check_value(a) <= check_value(b)
        except Exception as e:
            return ExcelError('#N/A', e)

func_dict = {
    "multiply": RangeCore.multiply,
    "divide": RangeCore.divide,
    "add": RangeCore.add,
    "substract": RangeCore.substract,
    "minus": RangeCore.minus,
    "is_equal": RangeCore.is_equal,
    "is_not_equal": RangeCore.is_not_equal,
    "is_strictly_superior": RangeCore.is_strictly_superior,
    "is_strictly_inferior": RangeCore.is_strictly_inferior,
    "is_superior_or_equal": RangeCore.is_superior_or_equal,
    "is_inferior_or_equal": RangeCore.is_inferior_or_equal,
}


def RangeFactory(cellmap = None):

    class Range(RangeCore):

        def __init__(self, address, values = None):
            super(Range, self).__init__(address, values, cellmap = cellmap)       

    return Range