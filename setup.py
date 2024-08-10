#! /usr/bin/python3

import sys
import subprocess
import importlib
import importlib.metadata
import re


CONFIG_GRASS_PATH = ''


class SetupStatus:
    # Paquetes usados en la aplicacion
    PACKAGES = {
        'numpy': {
            'version': '1.26.4',
            'module': 'numpy'
        },
        'python-cli-ui': {
            'version': '0.7.5',
            'module': 'ui'
        },
        'grass-session': {
            'version': '0.5',
            'module': 'grass-session'
        },
        'flopy': {
            'version': '3.3.1',
            'module': 'flopy'
        },
        'anytree': {
            'version': '2.8.0',
            'module': 'anytree'
        },
        'pyshp': {
            'version': '2.1.2',
            'module': 'pyshp'
        },
    }

    def __init__(self):
        self.PACKAGES = SetupStatus.PACKAGES.copy()
        self.process_lines = {}
        self.package_lines = {}
        self.reqs = {}

        self.packages_installed = []
        self.packages_missed = []

        # status
        self._MISSED_PAQ = False
        self._ERROR_REQ = False

        self.summary = SummaryStatus()

    def set_req_status(self, req: str, msg: str, status):
        line = {
            'req': req,
            'msg': msg,
            'status': status
        }

        if req in self.reqs:
            self.reqs[req].append(line)
        else:
            self.reqs[req] = [line]

        if status == 'ERROR':
            self._ERROR_REQ = True

    def get_packages(self):
        return self.PACKAGES

    def get_installed_packages(self):
        return self.packages_installed

    def get_missed_packages(self):
        return self.packages_missed
    
    def pkg_name_normalize(self, package):
        pkg = re.sub(r"[-_.]+", "-", package).lower()
        return pkg

    def check_packages(self):
        required = self.PACKAGES.keys()
        package_installed = {self.pkg_name_normalize(x.name) for x in importlib.metadata.distributions()}
        self.packages_missed = required - package_installed

        for package in required:
            self.package_lines[package] = {}
            if package in package_installed:
                self.package_lines[package]['status'] = 'FOUND'
            else:
                self.package_lines[package]['status'] = 'NOT FOUND'

        self._MISSED_PAQ = len(self.packages_missed) > 0

        return self._MISSED_PAQ

    def add_process_msg(self, package, msg, status, info=None):
        line = {
            'msg': msg,
            'status': status,
            'info': info
        }

        if package in self.process_lines:
            self.process_lines[package].append(line)
        else:
            self.process_lines[package] = [line]

    def get_summary(self):
        summary_text = self.summary.get_summary(reqs_status=self.reqs, packages_status=self.package_lines,
                                                process_status=self.process_lines)
        return summary_text


class SummaryStatus:
    def __init__(self, title: str = None):
        self.lines = []

        if title:
            line = {
                'msg': title,
                'status': False,  # 'OK', 'NOT FOUND', 'ERROR', 'INSTALLED'
                'level': 0
            }

            self.lines.append(line)

    def get_summary(self, reqs_status, packages_status, process_status):
        packages = SetupStatus.PACKAGES

        # Requirements Status
        msg_title = '{}\n{}\n{}'.format('=' * 25, 'Requirements Status', '=' * 25)
        self.lines.append(msg_title)
        for req_name in reqs_status:
            for req in reqs_status[req_name]:
                req_name, req_msg, req_status = req['req'], req['msg'], req['status']
                msg_info = '    (*) {}: [{}]'.format(req_msg, req_status)
                self.lines.append(msg_info)
        self.lines.append("\n")

        # Packages Status
        msg_title = '{}\n{}\n{}'.format('=' * 25, 'Packages Status', '=' * 25)
        self.lines.append(msg_title)
        for package in packages_status:
            package_status, package_version = packages_status[package]['status'], packages[package]['version']
            msg_info = '   (+) {} (version: {}): [{}]'.format(package, package_version, package_status)
            self.lines.append(msg_info)
        self.lines.append("\n")

        # Process Status
        msg_title = '{}\n{}\n{}'.format('-' * 25, 'Process Status', '-' * 25)
        self.lines.append(msg_title)
        for process_name in process_status:

            for process in process_status[process_name]:
                proc_info, proc_msg, proc_status = process['info'], process['msg'], process['status']

                if process_name in reqs_status:
                    msg_info = '    (*)=> {}: [{}]'.format(proc_msg, proc_status)
                else:
                    msg_info = '    (+)=> {}: [{}]'.format(proc_msg, proc_status)
                self.lines.append(msg_info)

                if proc_info:
                    msg_comment = '      {}'.format(proc_info)
                    self.lines.append(msg_comment)
            self.lines.append("\n")
        self.lines.append("\n")

        summary_text = '\n'.join(self.lines)

        return summary_text

# LD_LIBRARY_PATH=$(grass78 --config path)/lib
# os.putenv("LD_LIBRARY_PATH", "123")


def import_package(package, summary):
    packages = summary.get_packages()

    module = packages[package]['module']
    version = packages[package]['version']

    msg_search = 'Searching package: [{}]'.format(package)
    msg_install = 'Installing package: [{}] v{}'.format(package, version)

    try:
        importlib.import_module(module)
        summary.add_process_msg(package=package, msg=msg_search, status='FOUND')
    except ModuleNotFoundError:
        summary.add_process_msg(package=package, msg=msg_search, status='NOT FOUND')
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", '{}=={}'.format(package, version)])
            summary.add_process_msg(package=package, msg=msg_install, status='INSTALLED')
        except subprocess.CalledProcessError:
            msg_info = 'Need to be manually installed: pip3 install {}=={}'.format(package, version)
            summary.add_process_msg(package=package, msg=msg_install, status='NOT INSTALLED', info=msg_info)


def set_ld_library():
    import os
    os.environ['LD_LIBRARY_PATH'] = '/var/test2'


def grass_check():
    try:
        CONFIG_GRASS_PATH = subprocess.run(["grass83", "--config", "path"], shell=True)
        is_grass = True
    except subprocess.CalledProcessError:
        is_grass = False

    except FileNotFoundError:
        is_grass = False

    return is_grass


def pip_check():
    try:
        msg_info = '[*] pip is installed.'
        subprocess.run([sys.executable, "-m", "pip", '-h'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        is_pip = True
    except subprocess.CalledProcessError:
        is_pip = False

    return is_pip


def ld_library_check(grass_path: str = None):
    import os
    # os.putenv("LD_LIBRARY_PATH", "123")
    grass_lib_path = os.path.join(grass_path, '/lib')

    is_ld_var = os.getenv("LD_LIBRARY_PATH") and 'LD_LIBRARY_PATH' in os.environ

    return is_ld_var


def make_ld_var_config_file():
    try:
        status_msg = subprocess.call(['sh', './setup_ld_var.sh'])
        is_ok = True
    except subprocess.CalledProcessError:
        is_ok = False
    except FileNotFoundError:
        is_ok = False

    return is_ok

# LD_LIBRARY_PATH=$(grass78 --config path)/lib
# os.putenv("LD_LIBRARY_PATH", "123")


def setup_app():
    from sys import platform
    import os

    setup_status = SetupStatus()
    # Required checks
    # Grass Requirement
    is_grass = grass_check()
    if is_grass:
        msg_info = 'GRASS is installed.'
        setup_status.set_req_status(req='grass', msg=msg_info, status='OK')
    else:
        msg_info = 'GRASS need to be manually installed and its libs in PATH variable. (Linux hint: sudo apt-get install grass)'
        setup_status.set_req_status(req='grass', msg=msg_info, status='ERROR')

    # PIP Requirement
    is_pip = pip_check()
    if is_pip:
        msg_info = 'pip is installed.'
        setup_status.set_req_status(req='pip', msg=msg_info, status='OK')
    else:
        msg_info = 'pip need to be manually installed. (Linux hint: sudo apt-get install pip)'
        setup_status.set_req_status(req='pip', msg=msg_info, status='ERROR')

    # LD_LIBRARY_PATH check (warning in Linux)
    is_ld_var = ld_library_check(grass_path=CONFIG_GRASS_PATH)
    if is_ld_var:
        msg_info = '[LD_LIBRARY_PATH] environment variable is correctly set.'
        setup_status.set_req_status(req='LD_LIBRARY_PATH', msg=msg_info, status='OK')
    else:
        if platform == "linux" or platform == "linux2":
            is_ok = make_ld_var_config_file()

            msg_info = 'Making config file to set [LD_LIBRARY_PATH]'

            if not is_ok:
                setup_status.set_req_status(req='LD_LIBRARY_PATH', msg=msg_info, status='ERROR')
                grass_lib_path = os.path.join(CONFIG_GRASS_PATH, 'lib')
                msg_info = '[warning] [LD_LIBRARY_PATH] environment variable is not set. If you have problem to execute the application,' \
                           ' please set it to grass lib path ({}). ' \
                           '(Linux hint: export LD_LIBRARY_PATH=\'{}\')'.format(grass_lib_path, grass_lib_path)
                setup_status.set_req_status(req='LD_LIBRARY_PATH', msg=msg_info, status='ERROR')
            else:
                setup_status.set_req_status(req='LD_LIBRARY_PATH', msg=msg_info, status='OK')

    # package checks
    is_missed = setup_status.check_packages()
    if is_missed:
        packages_missed = setup_status.get_missed_packages()
        for package in packages_missed:
            import_package(package, summary=setup_status)
    summary_text = setup_status.get_summary()
    print(summary_text)


if __name__ == '__main__':
    setup_app()
