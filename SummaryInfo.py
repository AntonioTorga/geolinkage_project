import ui

import Utils
from Config import ConfigApp
from Errors import ErrorManager


class SummaryInfo:

    def __init__(self, prefix, errors: ErrorManager, config: ConfigApp):
        self.prefix = prefix
        self.config = config

        self.input_params = dict()
        self.process_lines = list()
        self.errors = errors

    def get_prefix(self):
        return self.prefix.upper()

    def set_input_param(self, param_name: str, param_value):
        self.input_params[param_name] = param_value

    def get_input_param(self, param_name: str):
        return self.input_params[param_name]

    def set_input_params(self, params: dict):
        for param_name in params:
            self.input_params[param_name] = params[param_name]

    def get_input_params(self):
        return self.input_params

    def print_input_params(self):
        params_str = ''

        for param_name in self.input_params:
            s = '     [{}]: {} \n'.format(param_name, self.input_params[param_name])
            params_str += s

        return params_str

    def set_process_line(self, msg_name: str, check_error: bool, **kwargs):
        msg_info = self.config.get_process_msg(msg_name=msg_name)
        status = 'ERROR' if check_error else 'OK'

        # apply parameters to message
        args_dict = {}
        for k, v in kwargs.items():
            args_dict[k] = v
        msg_info = msg_info.format(**args_dict)

        line = {
            'line': msg_info,
            'status': status,
        }
        self.process_lines.append(line)

    def get_process_lines(self, with_ui: bool = False):
        process_lines = self.process_lines

        if with_ui:
            process_lines = []
            for line_number, line in enumerate(self.process_lines):
                msg_info = Utils.insert_ui(text=line['line'], highlight_color=ui.darkred)

                status = '[{}]'.format(line['status'])
                if line['status'] == 'OK':
                    msg_status = Utils.insert_ui(text=status, highlight_color=ui.green)
                else:
                    msg_status = Utils.insert_ui(text=status, highlight_color=ui.red)

                newline = {
                    'line': msg_info,
                    'status': msg_status,
                }

                process_lines.append(newline)

        return process_lines

    def print_process_line(self):
        lines_str = ''

        for line_number, line in enumerate(self.process_lines):
            s = '  {}  [{}] \n'.format(line['line'], line['status'])
            lines_str += s

        return lines_str

    def get_errors(self, code: str = ''):
        return self.errors.get_errors(typ=self.prefix, code=code)

    def get_warnings(self, code: str = ''):
        return self.errors.get_warnings(typ=self.prefix, code=code)

    def print_errors(self):
        errors_list = self.get_errors()
        errors_str = ''

        for num, error in enumerate(errors_list):
            s = '[ERROR {}]: {} \n'.format(num+1, error)
            errors_str += s

        return errors_str

    def print_warnings(self):
        warnings_list = self.get_warnings()
        warnings_str = ''

        for num, warn in enumerate(warnings_list):
            s = '[WARNING {}]: {} \n'.format(num+1, warn)
            warnings_str += s

        return warnings_str

    def append_error(self, msg: str = None, msgs: list = None, typ: str = None, is_warn: bool = False, code: str = ''):
        typ = self.prefix if not typ else typ

        if is_warn:
            if msg:
                self.errors.append(msg=msg, typ=typ, is_warn=is_warn, code=code)
            elif msgs:
                for msg_str in msgs:
                    self.errors.append(msg=msg_str, typ=typ, is_warn=is_warn, code=code)
        else:
            if msg:
                self.errors.append(msg=msg, typ=typ, code=code)
            elif msgs:
                for msg_str in msgs:
                    self.errors.append(msg=msg_str, typ=typ, code=code)

    def get_title(self):
        return self.prefix.upper()
