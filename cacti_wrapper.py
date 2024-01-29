# in your metric, please set the accuracy you think CACTI's estimations are
import shutil
import math
import tempfile
import glob
import csv
import os
import subprocess
import threading
from accelergy.plug_in_interface.interface import *
import pickle as pkl
from datetime import datetime
CACTI_ACCURACY = 70

# -------------------------------------------------------------------------------
# CACTI7 wrapper for generating energy estimations for plain SRAM scraptchpad
# -------------------------------------------------------------------------------


SAVE_LAST_N_RECORDS: int = 50
CACTI_RECORDS_FILE = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), 'cacti_records.pkl')


class CactiWrapper(AccelergyPlugIn):
    """
    an estimation plug-in
    """
    # -------------------------------------------------------------------------------------
    # Interface functions, function name, input arguments, and output have to adhere
    # -------------------------------------------------------------------------------------

    def __init__(self, output_prefix=''):
        self.output_prefix = output_prefix
        # example primitive classes supported by this estimator
        self.supported_pc = ['SRAM', 'DRAM', 'cache']
        self.records = {}  # enable data reuse
        if os.path.exists(CACTI_RECORDS_FILE):
            try:
                with open(CACTI_RECORDS_FILE, 'rb') as f:
                    self.records = pkl.load(f)
            except:
                pass
        else:
            self.records = {}

    def get_name(self) -> str:
        return 'CACTI'

    def primitive_action_supported(self, query: AccelergyQuery) -> AccuracyEstimation:
        class_name = query.class_name
        attributes = query.class_attrs
        action_name = query.action_name
        arguments = query.action_args
        # Legacy interface dictionary has keys class_name, attributes, action_name, and arguments
        interface = query.to_legacy_interface_dict()

        if class_name in self.supported_pc:
            attributes_supported_function = class_name + '_attr_supported'
            if action_name == 'idle':
                return AccuracyEstimation(100)
            if getattr(self, attributes_supported_function)(attributes):
                action_supported_function = class_name + '_action_supported'
                accuracy = getattr(self, action_supported_function)(
                    action_name, arguments)
                if accuracy is not None:
                    return AccuracyEstimation(accuracy)
                self.logger.info(
                    'Action name %s for %s not supported.', action_name, class_name)
        else:
            self.logger.info(
                'Class name %s not supported. Supported classes: %s', class_name, self.supported_pc)
        return AccuracyEstimation(0)  # if not supported, accuracy is 0

    def estimate_energy(self, query: AccelergyQuery) -> Estimation:
        class_name = query.class_name
        attributes = query.class_attrs
        action_name = query.action_name
        arguments = query.action_args

        if action_name == 'idle':
            return Estimation(0, 'p')  # idle energy is zero

        # Legacy interface dictionary has keys class_name, attributes, action_name, and arguments
        interface = query.to_legacy_interface_dict()

        class_name = interface['class_name']
        query_function_name = class_name + '_estimate_energy'
        energy = getattr(self, query_function_name)(interface)
        return Estimation(energy, 'p')  # energy is in pJ

    def primitive_area_supported(self, query: AccelergyQuery) -> AccuracyEstimation:
        class_name = query.class_name
        attributes = query.class_attrs
        action_name = query.action_name
        arguments = query.action_args
        # Legacy interface dictionary has keys class_name, attributes, action_name, and arguments
        interface = query.to_legacy_interface_dict()

        if class_name == 'SRAM' or class_name == 'cache' or class_name == "DRAM":  # CACTI supports SRAM area estimation
            attributes_supported_function = class_name + '_attr_supported'
            if getattr(self, attributes_supported_function)(attributes):
                return AccuracyEstimation(CACTI_ACCURACY)
        else:
            self.logger.info(
                'Class name %s not supported. Supported classes: %s', class_name, ['SRAM', 'cache', 'DRAM'])

        return AccuracyEstimation(0)  # if not supported, accuracy is 0

    def estimate_area(self, query: AccelergyQuery) -> Estimation:
        class_name = query.class_name
        attributes = query.class_attrs
        action_name = query.action_name
        arguments = query.action_args
        # Legacy interface dictionary has keys class_name, attributes, action_name, and arguments
        interface = query.to_legacy_interface_dict()

        query_function_name = class_name + '_estimate_area'
        area = getattr(self, query_function_name)(interface)
        return Estimation(area, 'u^2')  # area is in um^2

    def search_for_cacti_exec(self):
        # search the current directory first, top-down walk
        this_dir, this_filename = os.path.split(__file__)
        for root, directories, file_names in os.walk(this_dir):
            if 'obj_dbg' not in root:
                for file_name in file_names:
                    if file_name == 'cacti':
                        cacti_exec_path = root + os.sep + file_name
                        cacti_exec_dir = os.path.dirname(cacti_exec_path)
                        return cacti_exec_dir
        raise FileNotFoundError(
            f'Could not find CACTI executable in {this_dir} or its subdirectories'
            f'Was CACTI built before installing the CACTI plug-in?'
        )

    # ----------------- DRAM related ---------------------------

    def DRAM_attr_supported(self, attributes):
        supported_attributes = {
            'type': ['DDR3', 'HBM2', 'GDDR5', 'LPDDR', 'LPDDR4']}
        if 'width' not in attributes:
            self.logger.info('Cannot estimate, missing width attribute.')
            return False
        if 'type' not in attributes:
            attributes['type'] = 'LPDDR4'

        if attributes['type'] not in supported_attributes['type']:
            self.logger.info('DRAM type %s not supported. Supported types: ',
                             attributes['type'], supported_attributes['type'])
        return True

    def DRAM_action_supported(self, action_name, arguments):
        supported_actions = ['read', 'write', 'leak', 'update']
        if action_name in supported_actions:
            return 95
        else:
            return None

    def DRAM_estimate_energy(self, interface):
        action_name = interface['action_name']
        width = interface['attributes']['width']
        energy = 0
        if 'read' in action_name or 'write' in action_name or 'update' in action_name:
            tech = interface['attributes'].get('type', 'LPDDR4')
            # Public data
            if tech == 'LPDDR4':
                energy = 8 * width
            # Malladi et al., ISCA'12
            elif tech == 'LPDDR':
                energy = 40 * width
            elif tech == 'DDR3':
                energy = 70 * width
            # Chatterjee et al., MICRO'17
            elif tech == 'GDDR5':
                energy = 14 * width
            elif tech == 'HBM2':
                energy = 3.9 * width
            else:
                energy = 0
        return energy

    def DRAM_area_supported(self, interface):
        return True

    def DRAM_estimate_area(self, interface):
        # DRAM area is zero
        return 0

    # ----------------- SRAM related ---------------------------
    def SRAM_populate_data(self, interface):
        attributes = interface['attributes']
        tech_node = attributes['technology']
        if isinstance(tech_node, str) and 'nm' in tech_node:
            tech_node = tech_node[:-2]  # remove the unit
        size_in_bytes = attributes['width'] * attributes['depth'] // 8
        wordsize_in_bytes = attributes['width'] // 8
        n_rw_ports = attributes['n_rdwr_ports'] + \
            attributes['n_rd_ports'] + attributes['n_wr_ports']
        desired_n_banks = attributes['n_banks']
        n_banks = desired_n_banks
        if not math.ceil(math.log2(n_banks)) == math.floor(math.log2(n_banks)):
            n_banks = 2**(math.ceil(math.log2(n_banks)))
        self.logger.info(f'Querying CACTI for request: {interface}')
        curr_dir = os.path.abspath(os.getcwd())
        cacti_exec_dir = self.search_for_cacti_exec()
        os.chdir(cacti_exec_dir)
        # check if the generated data already covers the case
        if not math.ceil(math.log2(desired_n_banks)) == math.floor(math.log2(desired_n_banks)):
            self.logger.warn(
                f'Cacti-plug-in... n_banks attribute is not a power of 2: {desired_n_banks}')
            self.logger.warn(f'corrected "n_banks": {n_banks}')
        cfg_file_name = self.output_prefix + datetime.now().strftime("%m_%d_%H_%M_%S") + \
            f'_{os.getpid()}' + '_SRAM.cfg'
        cfg_file_path = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), cfg_file_name)
        self.cacti_wrapper_for_SRAM(cacti_exec_dir, tech_node, size_in_bytes, wordsize_in_bytes, n_rw_ports,
                                    n_banks, cfg_file_path)
        for action_name in ['read', 'write', 'leak', 'update']:
            entry_key = (action_name, tech_node, size_in_bytes,
                         wordsize_in_bytes, n_rw_ports, desired_n_banks)
            if action_name == 'read':
                cacti_entry = ' Dynamic read energy (nJ)'  # nJ
            elif action_name == 'write' or action_name == 'update':
                cacti_entry = ' Dynamic write energy (nJ)'  # nJ
            else:
                cacti_entry = ' Standby leakage per bank(mW)'  # mW
            csv_file_path = cacti_exec_dir + '/' + cfg_file_name + '.out'
            # query Cacti
            with open(csv_file_path) as csv_file:
                reader = csv.DictReader(csv_file)
                row = list(reader)[-1]
                if not action_name == 'leak':
                    # original energy is in has nJ as the unit
                    energy = float(row[cacti_entry]) * 10 ** 3
                    self.logger.info(
                        'Cacti returned %f pJ for %s',  energy, action_name)
                else:
                    standby_power_in_w = float(
                        row[cacti_entry]) * 10 ** -3  # mW -> W
                    self.logger.info(
                        'Cacti returned %f W for %s', standby_power_in_w, action_name)
                    leak_energy_per_bank_in_j = standby_power_in_w * \
                        attributes['global_cycle_seconds']
                    leak_energy_per_bank_in_pj = leak_energy_per_bank_in_j * 10 ** 12
                    energy = leak_energy_per_bank_in_pj * n_banks
            # record energy entry
            self.records.update({entry_key: energy})

        # record area entry
        entry_key = ('area', tech_node, size_in_bytes,
                     wordsize_in_bytes, n_rw_ports, desired_n_banks)
        area = float(row[' Area (mm2)']) * 10**6  # area in micron squared
        self.records.update({entry_key: area})
        # all information recorded, no need for saving the file
        os.remove(csv_file_path)
        os.chdir(curr_dir)

    def SRAM_estimate_area(self, interface):
        attributes = interface['attributes']
        tech_node = attributes['technology']
        if isinstance(tech_node, str) and 'nm' in tech_node:
            tech_node = tech_node[:-2]  # remove the unit
        size_in_bytes = attributes['width'] * attributes['depth'] // 8
        if size_in_bytes == 0:
            # zero size SRAM will simply have zero energy and area
            return 0
        wordsize_in_bytes = attributes['width'] // 8
        n_rw_ports = attributes['n_rdwr_ports'] + \
            attributes['n_rd_ports'] + attributes['n_wr_ports']
        desired_n_banks = attributes['n_banks']
        desired_entry_key = ('area', tech_node, size_in_bytes,
                             wordsize_in_bytes, n_rw_ports, desired_n_banks)
        if desired_entry_key not in self.records:
            self.SRAM_populate_data(interface)
            self.save_records()
        area = self.records[desired_entry_key]
        return area

    def SRAM_estimate_energy(self, interface):
        # translate the attribute names into the ones that can be understood by Cacti
        attributes = interface['attributes']
        tech_node = attributes['technology']
        if isinstance(tech_node, str) and 'nm' in tech_node:
            tech_node = tech_node[:-2]  # remove the unit
        size_in_bytes = attributes['width'] * attributes['depth'] // 8
        if size_in_bytes == 0:
            # zero size SRAM will simply have zero energy and area
            return 0
        wordsize_in_bytes = attributes['width'] // 8
        n_rw_ports = attributes['n_rdwr_ports'] + \
            attributes['n_rd_ports'] + attributes['n_wr_ports']
        desired_n_banks = attributes['n_banks']
        desired_action_name = interface['action_name']
        desired_entry_key = (desired_action_name, tech_node, size_in_bytes,
                             wordsize_in_bytes, n_rw_ports, desired_n_banks)
        if desired_entry_key not in self.records:
            self.SRAM_populate_data(interface)
            self.save_records()

        energy = self.records[desired_entry_key]
        if desired_action_name != 'leak':
            args = interface['arguments'] or {}
            address_delta = args.get('address_delta', 1)
            data_delta = args.get('data_delta', 1)
            # rough estimate: address decoding takes 30%, memory_cell_access_energy takes 70%
            energy *= 0.3 * address_delta/desired_n_banks + 0.7 * data_delta
        return energy  # output energy is pJ

    def SRAM_attr_supported(self, attributes):
        tech_node = attributes['technology']
        if isinstance(tech_node, str) and 'nm' in tech_node:
            tech_node = tech_node[:-2]  # remove the unit
        size_in_bytes = attributes['width'] * attributes['depth'] // 8
        if size_in_bytes == 0:
            # zero size SRAM will simply have zero energy and area
            return True
        else:
            if size_in_bytes < 64:
                # Cacti only estimates energy for SRAM size larger than 64B (512b)
                self.logger.info(
                    'Cannot estimate, SRAM size is smaller than 64B (512b)')
            if int(tech_node) < 22 or int(tech_node) > 180:
                self.logger.info(
                    'Cannot estimate, technology node is not between 22nm to 180nm')
        return True

    def SRAM_action_supported(self, action_name, arguments):
        supported_action_names = ['read', 'write', 'leak', 'update']
        # Cacti ignores the arguments to the read and write actions
        if action_name in supported_action_names:
            return CACTI_ACCURACY  # Cacti accuracy
        else:
            self.logger.info(
                'Action name %s not supported. Supported actions: ', action_name, supported_action_names)
            return None

    def cacti_wrapper_for_SRAM(self, cacti_exec_dir, tech_node, size_in_bytes, wordsize_in_bytes, n_rw_ports, n_banks, cfg_file_path):
        # technology node described in um
        tech_node_um = float(int(tech_node)/1000)
        cache_size = size_in_bytes
        block_size = wordsize_in_bytes
        if int(wordsize_in_bytes) < 4:  # minimum line size in cacti is 32-bit/4-byte
            block_size = 4
        if int(cache_size) / int(block_size) < 64:
            self.logger.warn('intended SRAM size is smaller than 64 words')
            self.logger.warn(
                f'intended SRAM size: {cache_size} block size: {block_size}')
            # minimum scratchpad size: 64 words
            cache_size = int(block_size) * 64
            self.logger.warn(f'corrected SRAM size: {cache_size}')
        output_width = int(wordsize_in_bytes) * 8
        # assumes that all the ports in the plain scratchpad are read write ports instead of exclusive ports
        rw_ports = n_rw_ports
        if int(rw_ports) == 0:
            rw_ports = 1  # you must have at least one port
        cfg_file_name = os.path.split(cfg_file_path)[1]
        default_cfg_file_path = os.path.join(
            os.path.dirname(cfg_file_path), 'default_SRAM.cfg')
        populated_cfg_file_path = cacti_exec_dir + '/' + cfg_file_name
        shutil.copyfile(default_cfg_file_path, populated_cfg_file_path)
        self.logger.info(f'copy {default_cfg_file_path} to {populated_cfg_file_path}')
        f = open(populated_cfg_file_path, 'a+')
        f.write('\n############## User-Specified Hardware Attributes ##############\n')
        f.write('-size (bytes) ' + str(cache_size) + '\n')
        f.write('-read-write port  ' + str(rw_ports) + '\n')
        f.write('-block size (bytes) ' + str(block_size) + '\n')
        f.write('-technology (u) ' + str(tech_node_um) + '\n')
        f.write('-output/input bus width  ' + str(output_width) + '\n')
        f.write('-UCA bank ' + str(n_banks) + '\n')
        f.close()

        cacti_output = self.call_cacti(cacti_exec_dir, populated_cfg_file_path)

    # ----------------- cache related ---------------------------
    def cache_populate_data(self, interface):
        attributes = interface['attributes']
        tech_node = attributes['technology']
        if isinstance(tech_node, str) and 'nm' in tech_node:
            tech_node = tech_node[:-2]  # remove the unit
        size_in_bytes = attributes['size']
        blocksize_in_bytes = attributes['block_size']
        n_rw_ports = attributes['n_rdwr_ports'] + \
            attributes['n_rd_ports'] + attributes['n_wr_ports']
        desired_n_banks = attributes['n_banks']
        n_banks = desired_n_banks
        if not math.ceil(math.log2(n_banks)) == math.floor(math.log2(n_banks)):
            n_banks = 2**(math.ceil(math.log2(n_banks)))
        associativity = attributes['associativity']
        tag_size = attributes['tag_size']
        self.logger.debug(f'Querying CACTI for request: {interface}')
        curr_dir = os.path.abspath(os.getcwd())
        cacti_exec_dir = self.search_for_cacti_exec()
        os.chdir(cacti_exec_dir)
        # check if the generated data already covers the case
        if not math.ceil(math.log2(desired_n_banks)) == math.floor(math.log2(desired_n_banks)):
            self.logger.warn(
                f'n_banks attribute is not a power of 2: {desired_n_banks}')
            self.logger.warn(f'corrected "n_banks": {n_banks}')
        cfg_file_name = self.output_prefix + 'cache.cfg'
        cfg_file_path = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), cfg_file_name)
        self.cacti_wrapper_for_cache(cacti_exec_dir, tech_node, size_in_bytes, blocksize_in_bytes, n_rw_ports,
                                     n_banks, associativity, tag_size, cfg_file_path)
        for action_name in ['read_access', 'write_access', 'leak', 'update_access']:
            entry_key = (action_name, tech_node, size_in_bytes, blocksize_in_bytes,
                         n_rw_ports, desired_n_banks, associativity, tag_size)
            if action_name == 'read_access':
                cacti_entry = ' Dynamic read energy (nJ)'  # nJ
            elif action_name == 'write_access' or action_name == 'update_access':
                cacti_entry = ' Dynamic write energy (nJ)'  # nJ
            else:
                cacti_entry = ' Standby leakage per bank(mW)'  # mW
            csv_file_path = cacti_exec_dir + '/' + cfg_file_name + '.out'
            # query Cacti
            with open(csv_file_path) as csv_file:
                reader = csv.DictReader(csv_file)
                row = list(reader)[-1]
                if not action_name == 'leak':
                    # original energy is in has nJ as the unit
                    energy = float(row[cacti_entry]) * 10 ** 3
                    self.logger.info(
                        'Cacti returned %f pJ for %s',  energy, action_name)
                else:
                    standby_power_in_w = float(
                        row[cacti_entry]) * 10 ** -3  # mW -> W
                    self.logger.info(
                        'Cacti returned %f W for %s', standby_power_in_w, action_name)
                    leak_energy_per_bank_in_j = standby_power_in_w * \
                        attributes['global_cycle_seconds']
                    leak_energy_per_bank_in_pj = leak_energy_per_bank_in_j * 10 ** 12
                    energy = leak_energy_per_bank_in_pj * n_banks
            # record energy entry
            self.records.update({entry_key: energy})

        # record area entry
        entry_key = ('area', tech_node, size_in_bytes, blocksize_in_bytes,
                     n_rw_ports, desired_n_banks, associativity, tag_size)
        area = float(row[' Area (mm2)']) * 10**6  # area in micron squared
        self.records.update({entry_key: area})
        # all information recorded, no need for saving the file
        os.remove(csv_file_path)
        os.chdir(curr_dir)

    def cache_estimate_area(self, interface):
        attributes = interface['attributes']
        tech_node = attributes['technology']
        if isinstance(tech_node, str) and 'nm' in tech_node:
            tech_node = tech_node[:-2]  # remove the unit
        size_in_bytes = attributes['size']
        blocksize_in_bytes = attributes['block_size']
        n_rw_ports = attributes['n_rdwr_ports'] + \
            attributes['n_rd_ports'] + attributes['n_wr_ports']
        desired_n_banks = attributes['n_banks']
        associativity = attributes['associativity']
        tag_size = attributes['tag_size']
        desired_entry_key = ('area', tech_node, size_in_bytes, blocksize_in_bytes,
                             n_rw_ports, desired_n_banks, associativity, tag_size)
        if desired_entry_key not in self.records:
            self.cache_populate_data(interface)
            self.save_records()
        area = self.records[desired_entry_key]
        return area

    def cache_estimate_energy(self, interface):
        # translate the attribute names into the ones that can be understood by Cacti
        attributes = interface['attributes']
        tech_node = attributes['technology']
        if isinstance(tech_node, str) and 'nm' in tech_node:
            tech_node = tech_node[:-2]  # remove the unit
        size_in_bytes = attributes['size']
        blocksize_in_bytes = attributes['block_size']
        n_rw_ports = attributes['n_rdwr_ports'] + \
            attributes['n_rd_ports'] + attributes['n_wr_ports']
        desired_n_banks = attributes['n_banks']
        associativity = attributes['associativity']
        tag_size = attributes['tag_size']
        desired_action_name = interface['action_name']
        desired_entry_key = (desired_action_name, tech_node, size_in_bytes,
                             blocksize_in_bytes, n_rw_ports, desired_n_banks, associativity, tag_size)
        if desired_entry_key not in self.records:
            self.cache_populate_data(interface)
            self.save_records()

        energy = self.records[desired_entry_key]
        if desired_action_name != 'leak':
            args = interface['arguments'] or {}
            address_delta = args.get('address_delta', 1)
            data_delta = args.get('data_delta', 1)
            # rough estimate: address decoding takes 30%, memory_cell_access_energy takes 70%
            energy *= 0.3 * address_delta/desired_n_banks + 0.7 * data_delta
        else:
            standby_power_in_w = float(energy) * 10 ** -3  # mW -> W
            self.logger.info(
                'Cacti returned %f W for %s', standby_power_in_w, desired_action_name)
            leak_energy_per_bank_in_j = standby_power_in_w * \
                attributes['global_cycle_seconds']
            leak_energy_per_bank_in_pj = leak_energy_per_bank_in_j * 10 ** 12
            energy = leak_energy_per_bank_in_pj * desired_n_banks

        return energy  # output energy is pJ

    def cache_attr_supported(self, attributes):
        tech_node = attributes['technology']
        if isinstance(tech_node, str) and 'nm' in tech_node:
            tech_node = tech_node[:-2]  # remove the unit
        size_in_bytes = attributes['size']
        if size_in_bytes < 64:
            # Cacti only estimates energy for SRAM size larger than 64B (512b)
            return False
        if int(tech_node) < 22 or int(tech_node) > 180:
            return False  # Cacti only supports technology that is between 22nm to 180 nm
        return True

    def cache_action_supported(self, action_name, arguments):
        supported_action_names = ['read_access',
                                  'write_access', 'leak', 'update_access']
        # Cacti ignores the arguments to the read and write actions
        if action_name in supported_action_names:
            return CACTI_ACCURACY  # Cacti accuracy
        else:
            return None

    def call_cacti(self, cacti_exec_dir, populated_cfg_file_path):
        # create a temporary output file to redirect terminal output of cacti
        if os.path.isfile(cacti_exec_dir + 'tmp_output.txt'):
            os.remove(cacti_exec_dir + 'tmp_output.txt')
            
        tmpdir = tempfile.gettempdir()
        tmp_output = os.path.join(tmpdir, f'cacti_output_{os.getpid()}_{threading.get_ident()}.txt')

        # call cacti executable to evaluate energy consumption
        cacti_exec_path = cacti_exec_dir + '/cacti'
        exec_list = [cacti_exec_path, '-infile', populated_cfg_file_path]
        self.logger.info(f'Calling ' + ' '.join(exec_list))
        with open(tmp_output, 'w') as f:
            result = subprocess.call(exec_list, stdout=f, stderr=subprocess.STDOUT)
            
        accelergy_tmp_dir = os.path.join(tempfile.gettempdir(), 'accelergy')
        os.makedirs(accelergy_tmp_dir, exist_ok=True)
        if len(os.listdir(accelergy_tmp_dir)) > 20:
            shutil.rmtree(accelergy_tmp_dir, ignore_errors=True)
            os.mkdir(accelergy_tmp_dir)
        new_path = os.path.join(accelergy_tmp_dir, os.path.basename(populated_cfg_file_path) + '_' + datetime.now().strftime("%m_%d_%H_%M_%S"))
        shutil.copy(populated_cfg_file_path, new_path)
        self.logger.info(f'Moved {populated_cfg_file_path} to {new_path}')
        self.logger.info(f'CACTI output: {tmp_output}')
        if result != 0:
            raise Exception(f'CACTI failed with exit code {result}. Please check {tmp_output} for CACTI output.')
        os.remove(populated_cfg_file_path)
        return tmp_output
        

    def cacti_wrapper_for_cache(self, cacti_exec_dir, tech_node, size_in_bytes, blocksize_in_bytes, n_rw_ports, n_banks, associativity, tag_size, cfg_file_path):
        # technology node described in um
        tech_node_um = float(int(tech_node)/1000)
        cache_size = size_in_bytes
        block_size = blocksize_in_bytes
        if int(blocksize_in_bytes) < 4:  # minimum line size in cacti is 32-bit/4-byte
            block_size = 4
        if int(cache_size) / int(block_size) < 64:
            self.logger.warn(f'intended cache size is smaller than 64 words')
            self.logger.warn(
                f'intended cache size: {cache_size}, block size: {block_size}')
            # minimum scratchpad size: 64 words
            cache_size = int(block_size) * 64
            self.logger.warn(f'corrected cache size: {cache_size}')
        output_width = int(blocksize_in_bytes) * 8  # TODO fix this later
        # assumes that all the ports in the plain scratchpad are read write ports instead of exclusive ports
        rw_ports = n_rw_ports
        if int(rw_ports) == 0:
            rw_ports = 1  # you must have at least one port
        cfg_file_name = os.path.split(cfg_file_path)[1]
        default_cfg_file_path = os.path.join(
            os.path.dirname(cfg_file_path), 'default_SRAM.cfg')
        populated_cfg_file_path = cacti_exec_dir + '/' + cfg_file_name
        self.logger.debug("cacti_exec_dir: " + cacti_exec_dir)
        self.logger.debug("populated_cfg_file_path: " +
                          populated_cfg_file_path)
        shutil.copyfile(default_cfg_file_path,
                        cacti_exec_dir + '/' + cfg_file_name)
        f = open(populated_cfg_file_path, 'a+')
        f.write('\n############## User-Specified Hardware Attributes ##############\n')
        f.write('-size (bytes) ' + str(cache_size) + '\n')
        f.write('-associativity ' + str(associativity) + '\n')
        f.write('-read-write port  ' + str(rw_ports) + '\n')
        f.write('-tag_size (b)  ' + '\"default\"' + '\n')
        f.write('-block size (bytes) ' + str(block_size) + '\n')
        f.write('-technology (u) ' + str(tech_node_um) + '\n')
        f.write('-output/input bus width  ' + str(output_width) + '\n')
        f.write('-UCA bank count ' + str(n_banks) + '\n')
        f.close()
        
        cacti_output = self.call_cacti(cacti_exec_dir, populated_cfg_file_path)

    def save_records(self):
        keys = list(self.records.keys())
        keys_to_keep = keys[-SAVE_LAST_N_RECORDS:]
        self.records = {k: self.records[k] for k in keys_to_keep}
        try:
            with open(CACTI_RECORDS_FILE, 'wb') as f:
                pkl.dump(self.records, f)
        except Exception as e:
            self.logger.warning(f'Failed to write cache: {e}')


if __name__ == '__main__':
    from typing import OrderedDict
    x = {'class_name': 'SRAM', 'attributes': OrderedDict([('technology', '32nm'), ('width', 64), ('depth', 4), ('n_rdwr_ports', 1), (
        'area_share', 1), ('n_rd_ports', 0), ('n_wr_ports', 0), ('n_banks', 1), ('latency', '5ns')]), 'action_name': 'write', 'arguments': None}
    w = CactiWrapper()
    print(w.primitive_action_supported(x))
    print(w.estimate_energy(x))
