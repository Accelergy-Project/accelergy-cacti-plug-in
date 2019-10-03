CACTI_ACCURACY = 70  # in your metric, please set the accuracy you think CACTI's estimations are

#-------------------------------------------------------------------------------
# CACTI7 wrapper for generating energy estimations for plain SRAM scraptchpad
#-------------------------------------------------------------------------------
import subprocess, os, csv, glob, tempfile, math

class CactiWrapper:
    """
    an estimation plug-in
    """
    # -------------------------------------------------------------------------------------
    # Interface functions, function name, input arguments, and output have to adhere
    # -------------------------------------------------------------------------------------
    def __init__(self):
        self.estimator_name =  "Cacti"

        # example primitive classes supported by this estimator
        self.supported_pc = ['SRAM']
        self.energy_records = {} # enable data reuse

    def primitive_action_supported(self, interface):
        """
        :param interface:
        - contains four keys:
        1. class_name : string
        2. attributes: dictionary of name: value
        3. action_name: string
        4. arguments: dictionary of name: value

        :type interface: dict

        :return return the accuracy if supported, return 0 if not
        :rtype: int

        """
        class_name = interface['class_name']
        attributes = interface['attributes']
        action_name = interface['action_name']
        arguments = interface['arguments']

        if class_name in self.supported_pc:
            attributes_supported_function = class_name + '_attr_supported'
            if getattr(self, attributes_supported_function)(attributes):
                action_supported_function = class_name + '_action_supported'
                accuracy = getattr(self, action_supported_function)(action_name, arguments)
                if accuracy is not None:
                    return accuracy

        return 0  # if not supported, accuracy is 0

    def estimate_energy(self, interface):
        """
        :param interface:
        - contains four keys:
        1. class_name : string
        2. attributes: dictionary of name: value
        3. action_name: string
        4. arguments: dictionary of name: value

       :return the estimated energy
       :rtype float

        """
        class_name = interface['class_name']
        query_function_name = class_name + '_estimate_energy'
        energy = getattr(self, query_function_name)(interface)
        return energy

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

        # search the PATH variable: search the directories provided in the PATH variable. top-down walk
        PATH_lst = os.environ['PATH'].split(os.pathsep)
        for path in PATH_lst:
            for root, directories, file_names in os.walk(os.path.abspath(path)):
                for file_name in file_names:
                    if file_name == 'cacti':
                        cacti_exec_path = root + os.sep + file_name
                        cacti_exec_dir = os.path.dirname(cacti_exec_path)
                        return cacti_exec_dir

    def SRAM_estimate_energy(self, interface):
        # translate the attribute names into the ones that can be understood by Cacti
        attributes = interface['attributes']
        tech_node = attributes['technology']
        if 'nm' in tech_node:
            tech_node = tech_node[:-2]  # remove the unit
        size_in_bytes = attributes['width'] * attributes['depth'] // 8
        wordsize_in_bytes = attributes['width'] // 8
        n_rw_ports = attributes['n_rdwr_ports'] + attributes['n_rd_ports'] + attributes['n_wr_ports']
        n_banks = attributes['n_banks']
        desired_action_name = interface['action_name']
        desired_entry_key = (desired_action_name, tech_node, size_in_bytes, wordsize_in_bytes, n_rw_ports, n_banks)
        if desired_entry_key in self.energy_records:
            if desired_action_name == 'idle':
                energy = self.energy_records[desired_entry_key]
            else:
                address_delta = interface['arguments']['address_delta']
                data_delta = interface['arguments']['data_delta']
                if address_delta == 0 and data_delta == 0:
                    interpreted_entry_key = ('idle', tech_node, size_in_bytes, wordsize_in_bytes, n_rw_ports, n_banks)
                    energy = self.energy_records[interpreted_entry_key]
                else:
                    interpreted_entry_key = ('idle', tech_node, size_in_bytes, wordsize_in_bytes, n_rw_ports, n_banks)
                    idle_banks_energy = self.energy_records[interpreted_entry_key] * (n_banks- address_delta) / n_banks
                    active_banks_energy = self.energy_records[desired_entry_key] * address_delta / n_banks
                    energy = idle_banks_energy + active_banks_energy
        else:
            print('Info: CACTI plug-in... Querying CACTI for query:\n', interface)
            curr_dir = os.path.abspath(os.getcwd())
            cacti_exec_dir = self.search_for_cacti_exec()
            os.chdir(cacti_exec_dir)
            # check if the generated data already covers the case
            self.cacti_wrapper_for_SRAM(cacti_exec_dir, tech_node, size_in_bytes, wordsize_in_bytes, n_rw_ports,
                                        n_banks, interface)
            for action_name in ['read', 'write', 'idle']:
                entry_key = (action_name, tech_node, size_in_bytes, wordsize_in_bytes, n_rw_ports, n_banks)
                if action_name == 'read':
                    cacti_entry = ' Dynamic read energy (nJ)'   # nJ
                elif action_name =='write':
                    cacti_entry = ' Dynamic write energy (nJ)'  # nJ
                else:
                    cacti_entry = ' Standby leakage per bank(mW)' # mW
                csv_file_path = cacti_exec_dir + '/out.csv'
                # query Cacti
                with open(csv_file_path) as csv_file:
                    reader = csv.DictReader(csv_file)
                    row = list(reader)[-1]
                    if not action_name == 'idle':
                        energy = float(row[cacti_entry]) * 10**3# original energy is in has nJ as the unit
                    else:
                        standby_power_in_w = float(row[cacti_entry]) * 10**-3 # mW -> W
                        idle_energy_per_bank_in_j = standby_power_in_w * float(row[' Random cycle time (ns)']) * 10**-9
                        idle_energy_per_bank_in_pj = idle_energy_per_bank_in_j * 10**12
                        energy = idle_energy_per_bank_in_pj * n_banks
                # record new entry
                self.energy_records.update({entry_key: energy})
            energy = self.energy_records[desired_entry_key]
            os.remove(csv_file_path) # all information recorded, no need for saving the file
            os.chdir(curr_dir)
        return  energy  # output energy is pJ

    def SRAM_attr_supported(self, attributes):
        tech_node = attributes['technology']
        if 'nm' in tech_node:
            tech_node = tech_node[:-2]  # remove the unit
        size_in_bytes = attributes['width'] * attributes['depth'] // 8
        if size_in_bytes < 64:
            return False  # Cacti only estimates energy for SRAM size larger than 64B (512b)
        if int(tech_node) < 22 or int(tech_node) > 180:
            return False  # Cacti only supports technology that is between 22nm to 180 nm
        return True

    def SRAM_action_supported(self, action_name, arguments):
        supported_action_names = ['read', 'write', 'idle']
        # Cacti ignores the arguments to the read and write actions
        if action_name in supported_action_names:
            return CACTI_ACCURACY # Cacti accuracy
        else:
            return None

    def cacti_wrapper_for_SRAM(self, cacti_exec_dir, tech_node, size_in_bytes, wordsize_in_bytes, n_rw_ports, n_banks, original_request):
        tech_node = tech_node  # technology node described in nm
        cache_size = size_in_bytes
        line_size = wordsize_in_bytes
        if int(wordsize_in_bytes) < 4:  # minimum line size in cacti is 32-bit/4-byte
            line_size = 4
        if int(cache_size) / int(line_size) < 64:
            print('WARN: CACTI Plug-in...  intended cache size is smaller than 64 words')
            print('intended cache size:', cache_size, 'line size:', line_size)
            cache_size = int(line_size) * 64  # minimum scratchpad size: 64 words
            print('corrected cache size:', cache_size)
        if not math.ceil(math.log2(n_banks)) == math.floor(math.log2(n_banks)):
            print('WARN: CACTI Plug-in... "n_banks: %s" is not a power of 2'%(str(n_banks)))
            n_banks = 2**(math.floor(math.log2(n_banks)))
            print('corrected "n_banks": ', n_banks)
        associativity = 1  # plain scratchpad is a direct mapped cache
        rw_ports = n_rw_ports  # assumes that all the ports in the plain scratchpad are read wrtie ports instead of exclusive ports
        if int(rw_ports) == 0:
            rw_ports = 1  # you must have at least one port

        banks = n_banks  # number of banks you want to divide your scratchpad into, default is one
        excl_read_ports = 0  # assumes no exclusive ports of any type
        excl_write_ports = 0
        single_ended_read_ports = 0
        search_ports = 0

        # following three parameters are meaningful only for main memories
        page_sz = 0
        burst_length = 8
        pre_width = 8
        output_width = int(wordsize_in_bytes) * 8

        # to model special structure like branch target buffers, directory, etc.
        # change the tag size parameter
        # if you want cacti to calculate the tagbits, set the tag size to "default"
        specific_tag = 0
        tag_width = 0
        access_mode = 2  # 0 normal, 1 seq, 2 fast
        cache = 0  # scratch ram 0 or cache 1
        main_mem = 0

        # assign weights for CACTI optimizations
        obj_func_delay = 0
        obj_func_dynamic_power = 0
        obj_func_leakage_power = 1000
        obj_func_area = 0
        obj_func_cycle_time = 0

        # from CACTI example config...
        dev_func_delay = 20
        dev_func_dynamic_power = 100000
        dev_func_leakage_power = 100000
        dev_func_area = 1000000
        dev_func_cycle_time = 1000000

        ed_ed2_none = 2  # 0 - ED, 1 - ED^2, 2 - use weight and deviate
        temp = 300
        wt = 0  # 0 - default(search across everything), 1 - global, 2 - 5%
        # delay penalty, 3 - 10%, 4 - 20 %, 5 - 30%, 6 - low-swing
        data_arr_ram_cell_tech_flavor_in = 0  # 0(itrs-hp) 1-itrs-lstp(low standby power)
        data_arr_peri_global_tech_flavor_in = 0  # 0(itrs-hp)
        tag_arr_ram_cell_tech_flavor_in = 0  # itrs-hp
        tag_arr_peri_global_tech_flavor_in = 0  # itrs-hp
        interconnect_projection_type_in = 1  # 0 - aggressive, 1 - normal
        wire_inside_mat_type_in = 1  # 2 - global, 0 - local, 1 - semi-global
        wire_outside_mat_type_in = 1  # 2 - global
        REPEATERS_IN_HTREE_SEGMENTS_in = 1  # wires with repeaters
        VERTICAL_HTREE_WIRES_OVER_THE_ARRAY_in = 0
        BROADCAST_ADDR_DATAIN_OVER_VERTICAL_HTREES_in = 0
        force_wiretype = 1
        wiretype = 30
        force_config = 0
        ndwl = 1
        ndbl = 1
        nspd = 0
        ndcm = 1
        ndsam1 = 0
        ndsam2 = 0
        ecc = 0

        # create a temporary output file to redirect terminal output of cacti
        if os.path.isfile(cacti_exec_dir + 'tmp_output.txt'):
            os.remove(cacti_exec_dir + 'tmp_output.txt')
        temp_output =  tempfile.mkstemp()[0]
        # call cacti executable to evaluate energy consumption
        cacti_exec_path = cacti_exec_dir + '/cacti'
        exec_list = [cacti_exec_path,
                         str(cache_size),
                         str(line_size),
                         str(associativity),
                         str(rw_ports),
                         str(excl_read_ports),
                         str(excl_write_ports),
                         str(single_ended_read_ports),
                         str(search_ports),
                         str(banks),
                         str(tech_node),
                         str(output_width),
                         str(specific_tag),
                         str(tag_width),
                         str(access_mode),
                         str(cache),
                         str(main_mem),
                         str(obj_func_delay),
                         str(obj_func_dynamic_power),
                         str(obj_func_leakage_power),
                         str(obj_func_area),
                         str(obj_func_cycle_time),
                         str(dev_func_delay),
                         str(dev_func_dynamic_power),
                         str(dev_func_leakage_power),
                         str(dev_func_area),
                         str(dev_func_cycle_time),
                         str(ed_ed2_none),
                         str(temp),
                         str(wt),
                         str(data_arr_ram_cell_tech_flavor_in),
                         str(data_arr_peri_global_tech_flavor_in),
                         str(tag_arr_ram_cell_tech_flavor_in),
                         str(tag_arr_peri_global_tech_flavor_in),
                         str(interconnect_projection_type_in),
                         str(wire_inside_mat_type_in),
                         str(wire_outside_mat_type_in),
                         str(REPEATERS_IN_HTREE_SEGMENTS_in),
                         str(VERTICAL_HTREE_WIRES_OVER_THE_ARRAY_in),
                         str(BROADCAST_ADDR_DATAIN_OVER_VERTICAL_HTREES_in),
                         str(page_sz),
                         str(burst_length),
                         str(pre_width),
                         str(force_wiretype),
                         str(wiretype),
                         str(force_config),
                         str(ndwl),
                         str(ndbl),
                         str(nspd),
                         str(ndcm),
                         str(ndsam1),
                         str(ndsam2),
                         str(ecc)]
        temp_dir = tempfile.gettempdir()
        script_path = temp_dir + '/accelergy_cacti_temp.sh'
        print('Info: CACTI plug-in... Command line input saved to: ', script_path)
        f = open(script_path, 'a+')
        if len(f.readlines()) > 1000:
            print('WARN:  CACTI Plug-in... temp logs at: ', script_path, 'exceeds 1000 lines, delete file and create new one')
            os.remove(script_path)
            f = open(script_path, 'a+')
        f.write('\n ------------------------- ')
        f.write('Original Request: \n ' + str(original_request) + '\n')
        f.write(str())
        for i in exec_list:
            f.write(i + ' ')
        f.close()
        os.chmod(script_path, 0o775)
        subprocess.call(exec_list, stdout=temp_output)


