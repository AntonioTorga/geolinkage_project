from abc import abstractmethod, ABCMeta

from grass.pygrass.vector import VectorTopo

from utils.Utils import GrassCoreAPI, UtilMisc
from utils.Errors import ErrorManager
from processors.GeoKernel import GeoKernel
from utils.SummaryInfo import SummaryInfo
from utils.Config import ConfigApp
from utils.Protocols import MapFileManagerProtocol


class FeatureProcess(MapFileManagerProtocol, metaclass=ABCMeta):
    """
        It is the feature processors parent class. Contains the generic logic of all processors.
        Currently 4 processors are implemented for vector maps of: catchments, groundwater, rivers and demand sites.

        Imports a shapefile to convert it into a vector map in a GRASS session.
        Processes vector map geometries using GRASS tools.
        Validates that geometries found are present in the surface scheme (node map and arc map).
        Linking geometries with groundwater grid cells.
        Creates a vector map with its final grid metadata.
        Export the map with final grid using the ESRI Shapefile (SHP) format and metadata structure
        needed by WEAP: (row, col, GW, CATCH, RIVER, DS1, DS2, DS3, DS4)


        Attributes:
        ----------
        geo : GeoKernel
            Used to access geometries defined on surface scheme.

        cells : Dict[namedtuple<Cell>, Dict[str, Dict[str, str|int]]
            It is used to store cell-feature relationship. Because a cell can be intersected by more than one
            map geometry, access is given by: [cell] -> [geo_intersected] -> [cell_feature_relationship_data].
            Structure and values stored depends on feature type, so details are in the processor classes.

        cell_ids: Dict[namedtuple<Cell>, Dict[str, str|int|List<data>]]
            Store for each cell the geometry (or geometries) that be stored in final file.
            In case more than one geometry of the same feature type intersects the same cell, the criterion used to
            select it (or them) is implemented in '_cell_order_criteria_default(...)' method.
            The following data is stored:
                - 'number_of_data': columns number to use in final file.
                - 'cell_id': cell id . (id in GW grid's vector map)
                - 'row': cell row.
                - 'col': cell column.
                - 'data': list with the data (or data set) to be stored. It is obtained from 'cells' variable.

        _err : ErrorManager
            Stores and manage errors and warnings.

        stats : Dict[str, str]
            Stores basic statistics (# of geometry, # wells, etc.).

        summary : SummaryInfo
            Used to access the execution results (errors, warnings, input parameters, statistics.) generated by
            feature type and format them in a standard way.

        _feature_type : str
            Used to identify the feature type to process (default: self.config.type_names[self.__class__.__name__])

        _features_by_map : Dict[str, str]
            Stores geometry names by their vector map name. Indexed by vector name.


        Methods:
        -------
        run(self, linkage_name: str)
            Executes the correct tasks order to process the feature type. Imports map, validate it with surface scheme,
            and intersects feature map(s) with groundwater grid map ('linkage_name' parameter) to establish
            cell-gemetry relationship.

        import_maps(self, verbose: bool = False, quiet: bool = True)
            Imports ESRI Shapefile(s) as GRASS vector map(s).
            ('verbose' and 'quiet' parameters used for debugging).

        check_names_with_geo(self)
            Verifies that feature names of the main map exist in the surface scheme (arc and node maps).

        check_names_between_maps(self). En caso de que no exista lo reporta como error.
            Checks that feature names exist only on one map.
            It reports it as an error if it finds a name on two or more maps (for example, between informative DS maps).

        inter_map_with_linkage(self, linkage_name, snap='1e-12', verbose: bool = False, quiet: bool = True)
            Intersects a vector map with the groundwater grid vector, using a GRASS platform tool (v.overlay).
            The 'linkage_name' parameter identifies the final grid and the 'snap' parameter allows you to do more
            detailed (but slower) intersection.

        make_grid_cell(self)
            Stores cell-feature relationship using the intersection between a vector map and groundwater grid map.

        make_cell_data_by_main_map(self, map_name, inter_map_name, inter_map_geo_type)
            Create the structure that stores features data of a main map.
            A main map generates at least one mandatory column in the final file metadata (even if its value is NULL).
            This method must be overwritten by each class that inherits from it.

        make_cell_data_by_secondary_maps(self, map_name, inter_map_name, inter_map_geo_type)
            Create the structure that stores features data of a secondary map.
            A secondary map generates at least one informative column (non-mandatory) in the final file metadata.
            (Currently, this case happen for demand site areas maps.)
            This method must be overwritten by each class that inherits from it.

        get_data_to_save(self, cell, main_data: bool = True)
            Returns 'cell' data. The 'main_data' parameter has by default the value True, which referes to
             main map data.

        append_error(self, msg: str = None, msgs: list = None, typ: str = None, is_warn: bool = False, code: str = '')
            Logs an error with message (msg) or messages (msgs) parameters. The 'typ' parameter identifies feature type
            associated with the error (groundwater, catchment, demand_site, river, main).
            In case of being an error, 'is_warn' is False or True in warning case.
            The 'code' parameter is used to give a code to errors or warnings.

        get_summary(self)
            Returns an summary with input parameters used in processing, errors / warnings and
            associated statistics.

        """

    def __init__(self, geo: GeoKernel, config: ConfigApp = None, debug=None, err: ErrorManager = None):
        super(FeatureProcess, self).__init__(config=config, error=err)

        self.geo = geo
        self.config = config
        self._err = err

        self.cells = {}
        self.cell_ids = {}
        self.map_names = {}

        self._features_by_map = {}  # [feature_name] = [[map_name_1],... , [map_name_i]]
        self.cells_by_map = {}  # [map_name_i] = [cell_i_1, ..., cell_i_j]

        if debug is None:
            self.__debug = self.config.debug if self.config is not None else False

        self._feature_type = self.config.type_names[self.__class__.__name__]

        # stats
        self.stats = {}

        self.z_rotation = None
        self.x_ll = None  # real world model coords (lower left)
        self.y_ll = None  # real world model coords (lower left)

        self.summary = SummaryInfo(prefix=self.get_feature_type(), errors=err, config=self.config)

        self.config.set_columns_to_save(feature_type=self.get_feature_type(),
                                        columns_to_save=self.config.default_opts[self.get_feature_type()]['columns_to_save'])
        self.config.set_order_criteria(feature_type=self.get_feature_type(),
                                       order_criteria=self.config.default_opts[self.get_feature_type()]['order_criteria'])

    def set_origin(self, x_ll: float, y_ll: float, z_rotation: float):
        self.x_ll = x_ll
        self.y_ll = y_ll
        self.z_rotation = z_rotation

    def get_epsg(self):
        return self.config.get_epsg()

    def get_gisdb(self):
        return self.config.get_gisdb()

    def get_location(self):
        return self.config.get_location()

    def get_mapset(self):
        return self.config.get_mapset()

    @abstractmethod
    def run(self, linkage_name: str):
        pass

    def get_summary(self):
        return self.summary

    def get_feature_type(self):
        return self._feature_type

    @abstractmethod
    def set_data_from_geo(self):
        pass

    @abstractmethod
    def get_feature_id_by_name(self, feature_name):
        pass

    def set_feature_names_in_maps(self, imported: bool = True):
        map_names = self.map_names
        if imported:
            map_names = dict([(m, map_names[m]) for m in map_names if map_names[m]['imported']])

        for map_key in map_names:
            map_name = map_names[map_key]['name']

            vector_map = VectorTopo(map_name)
            vector_map.open('r')

            fields = self.get_needed_field_names(alias=self.get_feature_type())
            main_field, main_needed = fields['main']['name'], fields['main']['needed']

            for a in vector_map.viter('areas'):
                if a.cat is None or not a.attrs[main_field]:
                    # print("[ERROR - {}] ".format(gws_name), a.cat, a.id)
                    continue

                feature_name = a.attrs[main_field]

                if feature_name in self._features_by_map:
                    self._features_by_map[feature_name].add(map_name)
                else:
                    self._features_by_map[feature_name] = {map_name}

            vector_map.close()

    # @main_task
    def check_names_with_geo(self):
        self.set_data_from_geo()  # get the feature names in geo maps (node and arc)

        if len(self._features_by_map) == 0:
            self.set_feature_names_in_maps(imported=True)

        for feature_name in self._features_by_map.keys():
            feature_id = self.get_feature_id_by_name(feature_name)  # find [feature_name] in geo features
            map_names = ', '.join(self._features_by_map[feature_name])

            if not feature_id:  # not exists in geometries (arcs and nodes)
                msg_error = 'El nombre [{}] en los mapas [{}] no existe en las geometrias bases de arcos y nodos.'.format(
                    feature_name, map_names
                )
                self.append_error(msg=msg_error, typ=self.get_feature_type(), code='10')  # check error codes = 1[x]

        self.summary.set_process_line(msg_name='check_names_with_geo', check_error=self.check_errors(code='10'))

        return self.check_errors(code='10'), self.get_errors(code='10')

    # @main_task
    def check_names_between_maps(self):
        self.set_data_from_geo()  # get the feature names in geo maps (node and arc)

        if len(self._features_by_map) == 0:
            self.set_feature_names_in_maps(imported=True)

        check_maps = [f_name for f_name in self._features_by_map if len(self._features_by_map[f_name]) > 1]
        for feature_name in check_maps:
            map_names = ', '.join(self._features_by_map[feature_name])
            msg_error = 'El nombre [{}] se encuentra en mas de un mapa ([{}]) al mismo tiempo.'.format(
                feature_name, map_names
            )
            self.append_error(msg=msg_error, code='11', typ=self.get_feature_type())  # check error codes = 1[x]

        self.summary.set_process_line(msg_name='check_names_between_maps', check_error=self.check_errors(code='11'))

        return self.check_errors(code='11'), self.get_errors(code='11')

    @staticmethod
    def _cell_order_criteria_default(cell, cells_dict, by_field='area'):
        area_targets = cells_dict[cell]
        area_targets_sorted = sorted(area_targets.items(), key=lambda x: x[1][by_field], reverse=True)
        area_targets_sorted = [area_target for area_key, area_target in area_targets_sorted]

        return area_targets_sorted  # (key, data_key)

    def _set_cell(self, cell, area_name, data, by_field='area'):
        if cell in self.cells:
            # watch if exist catchment
            if area_name in self.cells[cell]:
                area_area = data[by_field]
                self.cells[cell][area_name][by_field] += area_area
            else:
                self.cells[cell][area_name] = data
        else:
            self.cells[cell] = {}

            self.cells[cell][area_name] = data

    def _set_cell_by_criteria(self, criteria_func, by_field='area'):
        # watch what is the best area by criteria for a cell
        for cell in self.cells:
            area_targets_ordered = criteria_func(cell, self.cells, by_field=by_field)

            self.cell_ids[cell] = {
                'number_of_data': len(area_targets_ordered),
                'cell_id': area_targets_ordered[0]['cell_id'],
                'row': cell.row,
                'col': cell.col,
                'data': area_targets_ordered
            }

    def get_cell_keys(self):
        if self.cell_ids:
            return self.cell_ids.keys()
        else:
            return []

    def get_cell_id_data(self, cell):
        data = None
        if cell in self.cell_ids:
            data = self.cell_ids[cell]

        return data

    def get_order_criteria_name(self) -> str:  # 'area' or 'length'
        return self.config.get_order_criteria(feature_type=self.get_feature_type())

    def get_columns_to_save(self) -> int:
        return self.config.get_columns_to_save(feature_type=self.get_feature_type())

    @abstractmethod
    def make_cell_data_by_main_map(self, map_name, inter_map_name, inter_map_geo_type):
        pass

    @abstractmethod
    def make_cell_data_by_secondary_maps(self, map_name, inter_map_name, inter_map_geo_type):
        pass

    def make_grid_cell(self):
        map_names = self.get_map_names(only_names=False, with_main_file=True, imported=True)
        main_map_name, main_map_path, main_map_inter = self.get_main_map_name(only_name=False)

        for map_name, map_path, map_inter in map_names:

            inter_map_name = self.get_inter_map_name(map_key=map_name)  # get the intersection map name
            inter_map_geo_type = self.get_inter_map_geo_type(map_key=map_name)

            if map_name == main_map_name:
                self.make_cell_data_by_main_map(map_name=map_name, inter_map_name=inter_map_name,
                                                inter_map_geo_type=inter_map_geo_type)
            else:
                self.make_cell_data_by_secondary_maps(map_name=map_name, inter_map_name=inter_map_name,
                                                      inter_map_geo_type=inter_map_geo_type)

            # watch what is the best area for a cell by criteria
            self._set_cell_by_criteria(criteria_func=self._cell_order_criteria_default,
                                       by_field=self.get_order_criteria_name())

        return self.check_errors(types=[self.get_feature_type()]), self.get_errors()

    def inter_map_with_linkage(self, linkage_name, snap='1e-12', verbose: bool = False, quiet: bool = True):
        map_names = self.get_map_names(only_names=False, with_main_file=True, imported=True)
        for map_name, path_name, inter_name in map_names:
            self._inter_map_with_linkage(map_name=map_name, linkage_name=linkage_name, output_name=inter_name,
                                         snap=snap, verbose=verbose, quiet=quiet)

        return self.check_errors(types=[self.get_feature_type()]), self.get_errors()

    # (*)
    # @main_task
    def _inter_map_with_linkage(self, map_name, linkage_name, output_name, snap='1e-12', verbose: bool = False, quiet: bool = True):
        _err = False

        # select only features with names
        if self.get_needed_field_names(alias=self.get_feature_type())['main']:
            col_query = self.get_needed_field_names(alias=self.get_feature_type())['main']['name']
            GrassCoreAPI.extract_map_with_condition(map_name, map_name + '_extract', col_query, '', '!=')
            map_name = map_name + '_extract'

        _err, _errors = GrassCoreAPI.inter_map_with_linkage(map_name=map_name, linkage_name=linkage_name,
                                                            output_name=output_name, snap=snap)

        if _err:
            self.append_error(msgs=_errors, typ=self.get_feature_type())

        self.summary.set_process_line(msg_name='_inter_map_with_linkage', check_error=self.check_errors(types=[self.get_feature_type()]),
                                      map_name=map_name, linkage_name=linkage_name, output_name=output_name)

        return self.check_errors(types=[self.get_feature_type()]), self.get_errors()

    def get_data_to_save(self, cell, main_data: bool = True):
        if main_data:
            main_map = self.get_main_map_name(only_name=True, imported=True)
            col_data = self.get_cell_data_by_map(map_name=main_map, cell=cell)
            col_names = self.get_column_to_export(alias=self.get_feature_type(), with_type=False)
            cols_number = self.config.get_columns_to_save(feature_type=self.get_feature_type())

            if col_data:
                if len(col_data) > cols_number and self.__class__.__name__ == 'DemandSiteProcess':
                    msg_error = "Error en la [celda=(r={}, c={})] para mapa [{}]. El numero a almacenar es [{}], " \
                                "pero no debe ser mayor que [{}]. Se considera sólo [{}]"\
                        .format(cell.row, cell.col, main_map, len(col_data), cols_number, cols_number)
                    self.append_error(msg=msg_error, typ=self.config.type_names[self.__class__.__name__], is_warn=True)

                values_to_save = min(cols_number, len(col_data))

                data = dict([(col_names[i], col_data[i]['name']) for i in range(values_to_save)])
                for j in range(cols_number-values_to_save):
                    data[col_names[cols_number-(j+1)]] = ''
            else:
                data = dict([(col_names[i], '') for i in range(cols_number)])
        else:
            # col_prefix = self.config.fields_db['linkage'][self.get_feature_type()]
            data = {}
            col_names = self.get_info_columns_to_export(feature_type=self.get_feature_type(), with_type=False)
            map_names = self.get_map_names(only_names=False, with_main_file=False, imported=True)
            for ind, (map_name, map_path, map_inter) in enumerate(map_names):
                cell_data = self.get_cell_data_by_map(map_name=map_name, cell=cell)

                data[col_names[ind]] = cell_data[0]['name'] if cell_data else ''

                if len(cell_data) > 1:
                    msg_error = 'El mapa [{}] tiene mas de un valor en la [celda: ({}, {})]. Se considera el primero: [{}]'\
                        .format(map_name, cell.row, cell.col, cell_data[0]['name'])
                    self.append_error(msg=msg_error, typ=self.config.type_names[self.__class__.__name__])

        return data

    def get_linkage_column(self, with_type: bool = False, truncate: int = 7):
        return self.get_column_to_export(alias=self.get_feature_type(), with_type=with_type, truncate=truncate)

    def get_cell_data_by_map(self, map_name: str, cell):
        ret = []
        if cell in self.cell_ids:
            ret = [d for d in self.cell_ids[cell]['data'] if d['map_name'] == map_name]
        return ret

    def import_maps(self, verbose: bool = False, quiet: bool = True):
        map_names = [m for m in self.get_map_names(only_names=False, with_main_file=True, imported=False) if m[1]]

        for map_name, path_name, inter_name in map_names:
            _err, _errors = self.make_vector_map(map_name=map_name)
            if _err:
                self.append_error(msgs=_errors, typ=self.get_feature_type())
            else:
                self.summary.set_process_line(msg_name='import_maps', check_error=_err,
                                              map_path=path_name, output_name=map_name)
                # check mandatory field
                # _err, _ = self.check_basic_columns(map_name=map_name)
                # if not _err:
                #     self.map_names[map_name]['imported'] = True

        # re-projecting map if exists lower left edge
        if self.x_ll is not None and self.y_ll is not None and self.z_rotation is not None:
            self.set_origin_in_map()

        return self.check_errors(types=[self.get_feature_type()]), self.get_errors()

    def set_origin_in_map(self):
        map_names = [m for m in self.get_map_names(only_names=False, with_main_file=True, imported=True) if m[1]]

        if self.x_ll is not None and self.y_ll is not None and self.z_rotation is not None:
            for map_name, path_name, inter_name in map_names:
                # get map lower left edge
                x_ini_ll, y_ini_ll = UtilMisc.get_origin_from_map(map_name=map_name)

                # set the new origin
                x_offset_ll = self.x_ll - x_ini_ll
                y_offset_ll = self.y_ll - y_ini_ll
                map_name_out = '{}_transform'.format(map_name)
                _err, _errors = UtilMisc.set_origin_in_map(map_name=map_name, map_name_out=map_name_out,
                                                           x_offset_ll=x_offset_ll, y_offset_ll=y_offset_ll, z_rotation=self.z_rotation)

                self.summary.set_process_line(msg_name='set_origin_in_map', check_error=_err,
                                              map_name=map_name, x_ll=self.x_ll, y_ll=self.y_ll, z_rot=self.z_rotation)
                if not _err:
                    self.set_map_name(map_name=map_name, map_path=path_name, map_new_name=map_name_out)
                else:
                    msg_error = 'Can not reproject map [{}] to x_ll=[{}], y_ll=[{}], z_rot=[{}]'.format(
                        map_name, self.x_ll, self.y_ll, self.z_rotation
                    )
                    self.append_error(msg=msg_error, typ=self.get_feature_type())

    def check_basic_columns(self, map_name: str):
        _err, _errors = False, []
        fields = self.get_needed_field_names(alias=self.get_feature_type())

        for field_key in [field for field in fields if fields[field]]:
            field_name = fields[field_key]['name']
            needed = fields[field_key]['needed']

            __err, __errors = GrassCoreAPI.check_basic_columns(map_name=map_name, columns=[field_name], needed=[needed])

            self.summary.set_process_line(msg_name='check_basic_columns', check_error=__err,
                                          map_name=map_name, columns=field_name)
            if needed:
                self.append_error(msgs=__errors, is_warn=False, typ=self.get_feature_type(), code='20')  # error code = 20
            else:
                self.append_error(msgs=__errors, is_warn=True, typ=self.get_feature_type(), code='20')

        return self.check_errors(code='20'), self.get_errors(code='20')

    def set_map_names(self):
        feature_type = self.get_feature_type()
        for map_name, map_path, is_main in self.get_feature_file_paths(feature_type=feature_type):
            self.set_map_name(map_name=map_name, map_path=map_path, is_main_file=is_main)





