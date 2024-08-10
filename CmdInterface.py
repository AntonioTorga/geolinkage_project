import argparse
import subprocess
import sys
import ui

from grass_session import Session
from grass.script.utils import try_rmdir

from utils.Utils import UtilMisc
from AppKernel import AppKernel
from InterfaceApp import InterfaceApp
from utils.SummaryInfo import SummaryInfo


def add_grass_to_path():
    try:
        CONFIG_GRASS_PATH = subprocess.run(["grass83", "--config", "path"], shell=True)
    except FileNotFoundError as e:
        CONFIG_GRASS_PATH = None

    if CONFIG_GRASS_PATH is not None:
        sys.path.append(CONFIG_GRASS_PATH + '/etc/python')
        sys.path.append(CONFIG_GRASS_PATH + '/lib')
    else:
        msg_not_found = "It can be found GRASS (grass78) program. Please add absolute path of python executable and 'python/lib'."
        print("[ERROR] {}",format(msg_not_found))

    return CONFIG_GRASS_PATH


def print_summary(summary: SummaryInfo):
    prefix = summary.get_prefix()

    inputs = summary.print_input_params()
    real_lines = summary.get_process_lines(with_ui=True)
    errors = summary.print_errors()
    warnings = summary.print_warnings()

    if inputs:
        UtilMisc.show_title(msg_title='[{}] INPUT PARAMETERS AND STATS'.format(prefix), title_color=ui.brown)

        inputs_lines = inputs.splitlines()
        for line in inputs_lines:
            msg_info = UtilMisc.insert_ui(text=line, highlight_color=ui.lightgray)
            ui.info(ui.red, '  => ', ui.white, ui.faint, *msg_info)

    if real_lines:
        UtilMisc.show_title(msg_title='[{}] PROCESSING STATUS'.format(prefix), title_color=ui.brown)
        for line_number, line in enumerate(real_lines):
            msg_info = line['line']
            msg_status = line['status']

            ui.info(ui.green, ui.bold, ':: ', ui.white, ui.faint, *msg_info, *msg_status)

    if warnings:
        UtilMisc.show_title(msg_title='[{}] WARNINGS'.format(prefix), title_color=ui.brown)
        warning_lines = warnings.splitlines()
        for line in warning_lines:
            msg_info = UtilMisc.insert_ui(text=line)
            ui.info(*msg_info)

    if errors:
        UtilMisc.show_title(msg_title='[{}] ERRORS'.format(prefix), title_color=ui.brown)
        error_lines = errors.splitlines()
        for line in error_lines:
            msg_info = UtilMisc.insert_ui(text=line)
            ui.info(*msg_info)


def cleanup(location: str):
    try_rmdir(location)


class CmdInterface(InterfaceApp):
    """
        It takes care of everything related to the input parameters, GRASS session generation used by the processing
        engine and displays execution results in the user's console or terminal.

        * Config file: ./config/config.json


        Attributes:
        ----------
        _config_opts : Dict[str, Dict | str]
            Class attribute that stores the input keywords and their meaning. This value is obtained from the
            configuration file.


        Methods:
        -------
        run(self)
            (Inherited from InterfaceApp) Executes the features processing engine with input parameters and options.

        check_args(self)
            (Inherited from InterfaceApp) Configures and parses the necessary arguments of the features processing
            engine execution.

        print_catchment_summary(self)
            (Inherited from InterfaceApp) Prints the catchment processor execution results.

        print_gw_summary(self)
            (Inherited from InterfaceApp) Prints the groundwater processor execution results.

        print_ds_summary(self)
            (Inherited from InterfaceApp) Prints the demand site processor execution results.

        print_river_summary(self)
            (Inherited from InterfaceApp) Prints the river processor execution results.

        print_main_summary(self)
            (Inherited from InterfaceApp) Prints the application execution general results.

        print_input_summary(self)
            (Inherited from InterfaceApp) Prints the input parameters that the user entered.

        print_errors(self)
            (Inherited from InterfaceApp) Prints errors that happen when processing input parameters or some
            other error related to the user interface.


        Examples:
        --------
        >>> gisdb, location, mapset = '/tmp', 'loc_test', 'PERMANENT'
        >>> app = AppKernel(gisdb=gisdb, location=location, mapset=mapset)
        >>> interface_app = CmdInterface(app=app, _gisdb=gisdb, _location=location, _mapset=mapset)

        >>> # get input parameters
        >>> options, flags, parser = interface_app.check_args()
        >>> linkage_in_file = options['linkage_in']
        >>> linkage_out_folder = options['linkage_out_folder']
        >>> node_file = options['node']
        >>> arc_file = options['arc']
        >>> catchment_file = options['catchment']
        >>> gw_file = options['gw']
        >>> ds_folder = options['ds_folder']
        >>> catchment_field = options['catchment_field']
        >>> gw_field = options['gw_field']
        >>> ds_field = options['ds_field']
        >>> epsg_in=options['epsg_code']

        >>> if flags['g']:  # make linkage grid using MODFLOW model and flopy
        >>>     interface_app.set_gw_model_coords_lower_left(coords_ll=options['coords_ll'])  # (x_ll, y_ll) in gw model
        >>>     interface_app.set_z_rotation(z_rotation=options['zrotation'])

        >>>     if interface_app.x_ll is not None and interface_app.y_ll is not None and interface_app.z_rotation is not None:
        >>>         app.set_origin(x_ll=interface_app.x_ll, y_ll=interface_app.y_ll, z_rotation=interface_app.z_rotation)

        >>>         interface_app.set_linkage_in_folder(linkage_in_folder=options['linkage_in_folder'])
        >>>         interface_app.set_gw_model(gw_model_file=options['gw_model'])

        >>>         # make grid with flopy
        >>>         interface_app.get_linkage_grid_by_model()
        >>>         linkage_in_file = interface_app.linkage_in_file

        >>> interface_app.set_feature_fields(catchment_field=catchment_field, gw_field=gw_field, ds_field=ds_field)
        >>> interface_app.set_required_paths(linkage_in_file=linkage_in_file, linkage_out_folder=linkage_out_folder,
        >>>                                      node_file=node_file, arc_file=arc_file)
        >>> interface_app.set_additional_paths(catchment_file=catchment_file, gw_file=gw_file, ds_folder=ds_folder)

        >>> if not interface_app.check_errors():
        >>>     app.set_epsg(epsg_code=epsg_in)
        >>>     interface_app.run()

        >>>     interface_app.print_input_summary()
        >>>     interface_app.print_main_summary()
        >>>     interface_app.print_catchment_summary()
        >>>     interface_app.print_gw_summary()
        >>>     interface_app.print_ds_summary()
        >>>     interface_app.print_river_summary()

        """

    _config_opts = InterfaceApp.config["COMMAND INTERFACE"]["UI OPTIONS"]

    def __init__(self, app: AppKernel = None, _gisdb: str = None, _location: str = None, _mapset: str = None):
        super().__init__(app=app, _gisdb=_gisdb, _location=_location, _mapset=_mapset)

    def print_catchment_summary(self):
        summary = self.app.get_catchment_summary()
        print_summary(summary)

    def print_gw_summary(self):
        summary = self.app.get_gw_summary()
        print_summary(summary)

    def print_ds_summary(self):
        summary = self.app.get_ds_summary()
        print_summary(summary)

    def print_river_summary(self):
        summary = self.app.get_river_summary()
        print_summary(summary)

    def print_main_summary(self):
        summary = self.app.get_main_summary()
        print_summary(summary)

    def print_geo_summary(self):
        summary = self.app.get_geo_summary()
        print_summary(summary)

    def print_errors(self):
        if self.errors:
            for err in self.errors:
                msg_info = UtilMisc.insert_ui(text=err)
                ui.info(ui.red, ui.bold, ':: ', ui.white, ui.faint, *msg_info)
                #ui.info(ui.green, ui.bold, '=> ', ui.white, ui.faint, *msg_info)

    def print_input_summary(self):
        space = ' '

        l1 = '  {p1:>22} {p_v1:<15} {e:^6} {p2:>10} {p_v2:<10} {e:^6} {p3:>25} {p_v3:<30}'.format(
            p1='[LOCATION]:', p_v1='/tmp/{}'.format(self.location), p2='[MAPSET]:', p_v2='PERMANENT',
            p3='*[EPSG CODE]:', p_v3=self.epsg_code, e=space)

        l2 = '  {p1:>22} {p_v1:<100}'.format(p1='*[LINKAGE-IN FILE]:', p_v1=self.linkage_in_file, e=space)
        l3 = '  {p1:>22} {p_v1:<100}'.format(p1='*[LINKAGE-OUT FOLDER]:', p_v1=self.linkage_out_folder, e=space)
        l4 = '  {p1:>22} {p_v1:<100}'.format(p1='*[NODE FILE]:', p_v1=self.node_file, e=space)
        l5 = '  {p1:>22} {p_v1:<100}'.format(p1='*[ARC FILE]:', p_v1=self.arc_file, e=space)

        l6 = '  {p1:>22} {p_v1:<60} {e:^6} {p2:>22} {p_v2:<20}'.format(
            p1='[CATCHMENT FILE]:', p_v1=self.catchment_file, p2='[CATCHMENT COLUMN]:', p_v2=self.catchment_field,
            e=space)
        l7 = '  {p1:>22} {p_v1:<60} {e:^6} {p2:>22} {p_v2:<20}'.format(
            p1='[GW FILE]:', p_v1=self.gw_file, p2='[GW COLUMN]:', p_v2=self.gw_field, e=space)
        l8 = '  {p1:>22} {p_v1:<60} {e:^6} {p2:>22} {p_v2:<20}'.format(
            p1='[DS FOLDER]:', p_v1=self.ds_folder, p2='[DS COLUMN]:', p_v2=self.ds_field, e=space)

        lines = f'{l1} \n\r {l2} \n\r {l3} \n\r {l4} \n\r {l5} \n\r {l6} \n\r {l7} \n\r {l8} \n\r'

        UtilMisc.show_title(msg_title='INPUT PARAMETERS', title_color=ui.darkred)
        print(lines)

    def print_groundwater_model_info(self, gw_model):
        # get groundwater model info
        info = self.get_model_info(gw_model=gw_model)

        # print model info
        ui.info_section('INITIAL MODEL INFO:')
        summary = [[(ui.faint, concept), (ui.faint, ui.green, info[concept])] for concept in info]
        ui.info_table(summary, headers=[])

    def get_linkage_grid_by_model(self, linkage_file_name: str = 'linkage_in.shp'):
        msgs_it = self.make_linkage_grid(linkage_file_name=linkage_file_name)
        for msg in msgs_it:
            # TODO: We need to differentiate between error and info (Class SummaryProcess?)
            msg_info = UtilMisc.insert_ui(text=msg)
            ui.info(ui.green, ui.bold, '=> ', ui.white, ui.faint, *msg_info)

    def check_args(self):
        _err, _errors = False, []
        _result = {}

        my_parser = argparse.ArgumentParser(description=CmdInterface.config["COMMAND INTERFACE"]["tool_description"],
                                            allow_abbrev=False)

        # Add the arguments
        _opts = self._config_opts
        for opt_key in _opts:
            cmd = _opts[opt_key]['cmd']
            shortcut = _opts[opt_key]['shortcut']
            cmd_type = _opts[opt_key]['cmd_type']
            action = 'store' if cmd_type == 'key' else 'store_true'
            num_args = 1 if cmd_type == 'key' else 0
            # my_parser.add_argument(opt_key, metavar=opt_key, type=str, help=_opts[opt_key]['help'], required=False)
            if cmd_type == 'key':
                my_parser.add_argument(shortcut,
                                       cmd,
                                       action=action,
                                       help=_opts[opt_key]['help'],
                                       required=False,
                                       # metavar=_opts[opt_key]['msg_input'],
                                       nargs=num_args)
            else:
                my_parser.add_argument(shortcut,
                                       cmd,
                                       action=action,
                                       help=_opts[opt_key]['help'],
                                       required=False)

        # Execute the parse_args() method
        args = my_parser.parse_args()

        args = dict(args._get_kwargs())
        options = {
            'epsg_code': args['epsg_code'][0] if args['epsg_code'] else '',

            'linkage_in_folder': args['linkage_in_folder'][0] if args['linkage_in_folder'] else '',
            'gw_model': args['gw_model'][0] if args['gw_model'] else '',
            'coords_ll': args['coords_ll'][0] if args['coords_ll'] else '',
            'zrotation': args['zrotation'][0] if args['zrotation'] else '',

            'linkage_in': args['linkage_in'][0] if args['linkage_in'] else '',
            'linkage_out_folder': args['linkage_out_folder'][0] if args['linkage_out_folder'] else '',
            'node': args['node'][0] if args['node'] else '',
            'arc': args['arc'][0] if args['arc'] else '',
            'catchment': args['catchment'][0] if args['catchment'] else '',
            'gw': args['gw'][0] if args['gw'] else '',
            'ds_folder': args['ds_folder'][0] if args['ds_folder'] else '',
            'catchment_field': args['catchment_field'][0] if args['catchment_field'] else 'Catchment',
            'gw_field': args['gw_field'][0] if args['gw_field'] else 'GW',
            'ds_field': args['ds_field'][0] if args['ds_field'] else 'DS',
        }
        flags = {'g': args['g'] if args['g'] else False}

        return options, flags, my_parser

    def run(self):
        try:
            _err, _errors = self.app.run()
        except subprocess.CalledProcessError as e:
            if e.output:
                msg_error = e.output
            elif e.msg:
                msg_error = e.msg
            else:
                msg_error = ''

            msg_errors = '\n'.join(msg_error.replace('\\n', '\n').split('\n'))
            ui.info('\n\r', ui.bold, ui.red, ':: ', ui.faint, ui.darkred, '{}. \n\r\n\r'.format(msg_errors))
            ui.info('\n\r', ui.bold, ui.red, ':: ', ui.faint, ui.darkred, 'ERROR - EXECUTION FINISHED')

            sys.exit(-1)


def main(location: str):
    ui.setup(verbose=True, quiet=False, color="always")  # the kernel app code use ui package

    # init interface
    gisdb = InterfaceApp.config["COMMAND INTERFACE"]["gisdb"]
    mapset = InterfaceApp.config["COMMAND INTERFACE"]["mapset"]
    app = AppKernel(gisdb=gisdb, location=location, mapset=mapset)
    interface_app = CmdInterface(app=app, _gisdb=gisdb, _location=location, _mapset=mapset)

    options, flags, parser = interface_app.check_args()

    # set the EPSG code
    interface_app.set_epsg_code(epsg_code=options['epsg_code'])
    app.set_epsg(epsg_code=options['epsg_code'])

    # get or make the linkage-in shapefile
    if flags['g']:  # make linkage grid using MODFLOW model and flopy
        linkage_in_name_default = 'linkage_in_from_model.shp'

        linkage_in_folder = options['linkage_in_folder']
        gw_model_file = options['gw_model']

        interface_app.set_gw_model_coords_lower_left(coords_ll=options['coords_ll'])  # (x_ll, y_ll) in gw model
        interface_app.set_z_rotation(z_rotation=options['zrotation'])

        if interface_app.x_ll is not None and interface_app.y_ll is not None and interface_app.z_rotation is not None:
            app.set_origin(x_ll=interface_app.x_ll, y_ll=interface_app.y_ll, z_rotation=interface_app.z_rotation)

        if not (linkage_in_folder and gw_model_file):
            msg_error = 'Option [-g] requires of [gw_model], [linkage_in_folder]'
            ui.info('\n\r', ui.bold, ui.red, ':: ', ui.faint, ui.darkred, msg_error)

        # check if paths exist
        exist_files, exist_folders = UtilMisc.check_paths_exist(folders=[linkage_in_folder], files=[gw_model_file])
        if exist_folders[0][0] and exist_files[0][0]:
            interface_app.set_linkage_in_folder(linkage_in_folder=options['linkage_in_folder'])
            interface_app.set_gw_model(gw_model_file=options['gw_model'])

            # make grid with flopy
            interface_app.get_linkage_grid_by_model(linkage_file_name=linkage_in_name_default)

            if not interface_app.check_errors():  # if not error:
                linkage_in_file = interface_app.linkage_in_file  # os.path.join(linkage_in_folder, linkage_in_name_default)
            else:
                parser.print_help(sys.stderr)
                interface_app.print_errors()
                sys.exit(1)
                #ui.info('\n\r', ui.bold, ui.red, ':: ', ui.faint, ui.darkred, msg_error)
        elif not (exist_folders[0][0] or exist_files[0][0]):
            parser.print_help(sys.stderr)
            ui.info('\n\r', ui.bold, ui.red, ':: ', ui.faint, ui.darkred, exist_folders[0][1])
            ui.info('\n\r', ui.bold, ui.red, ':: ', ui.faint, ui.darkred, exist_files[0][1])
            sys.exit(1)
        elif not exist_folders[0][0]:
            parser.print_help()
            ui.info('\n\r', ui.bold, ui.red, ':: ', ui.faint, ui.darkred, exist_folders[0][1])
            sys.exit(1)
        else:
            parser.print_help(sys.stderr)
            ui.info('\n\r', ui.bold, ui.red, ':: ', ui.faint, ui.darkred, exist_files[0][1])
            sys.exit(1)
    else:  # using an existing linkage-in shapefile
        linkage_in_file = options['linkage_in']

    # get input parameters
    linkage_out_folder = options['linkage_out_folder']
    node_file = options['node']
    arc_file = options['arc']
    catchment_file = options['catchment']
    gw_file = options['gw']
    ds_folder = options['ds_folder']
    catchment_field = options['catchment_field']
    gw_field = options['gw_field']
    ds_field = options['ds_field']

    interface_app.set_feature_fields(catchment_field=catchment_field, gw_field=gw_field,
                                     ds_field=ds_field)  # set fields

    # set paths
    interface_app.set_required_paths(linkage_in_file=linkage_in_file, linkage_out_folder=linkage_out_folder,
                                     node_file=node_file, arc_file=arc_file)
    interface_app.set_additional_paths(catchment_file=catchment_file, gw_file=gw_file, ds_folder=ds_folder)

    # run kernel code
    if not interface_app.check_errors():

        tmp_location = UtilMisc.generate_word(length=5, prefix='loc_')
        # tmp_location = interface_app.location
        # with Session(gisdb="/home/pc/gisdata/grassdata", location="test", mapset='pc', create_opts=""):
        with Session(gisdb=interface_app.gisdb, location=interface_app.location, create_opts="EPSG:{}".format(interface_app.epsg_code)) as sess:
            # atexit.register(cleanup, location=location)
            interface_app.run()

            interface_app.print_input_summary()
            interface_app.print_main_summary()
            interface_app.print_geo_summary()
            interface_app.print_catchment_summary()
            interface_app.print_gw_summary()
            interface_app.print_ds_summary()
            interface_app.print_river_summary()
    else:
        parser.print_help(sys.stderr)
        # interface_app.print_errors()


if __name__ == "__main__":
    # add_grass_to_path()
    location = UtilMisc.generate_word(length=5, prefix=InterfaceApp.config["COMMAND INTERFACE"]["location_prefix"])

    main(location=location)




