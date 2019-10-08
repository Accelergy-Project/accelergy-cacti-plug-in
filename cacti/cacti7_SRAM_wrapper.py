# -------------------------------------------------------------------------------
# CACTI7 wrapper for generating energy estimations for plain SRAM scraptchpad
# -------------------------------------------------------------------------------
import subprocess, sys, os

def cacti7_wrapper_for_SRAM(tech_node, size_in_bytes, wordsize_in_bytes, n_rw_ports, n_banks):
    tech_node = tech_node  # technology node described in nm
    cache_size = size_in_bytes
    line_size = wordsize_in_bytes
    if int(wordsize_in_bytes) < 4:  # minimum line size in cacti is 32-bit/4-byte
        line_size = 4
    if int(cache_size) / int(line_size) < 64:
        print('WARN: intended cache size is smaller than 64 words')
        print('intended cache size:', cache_size, 'line size:', line_size)
        cache_size = int(line_size) * 64  # minimum scratchpad size: 64 words
        print('corrected cache size:',cache_size)
    associativity = 1  # plain scratchpad is a direct mapped cache
    rw_ports = n_rw_ports  # assumes that all the ports in the plain scratchpad are read wrtie ports instead of exclusive ports
    if int(rw_ports) == 0:
        rw_ports = 1  # you must have at least one port

    banks = n_banks  # number of banks you want to divide your srachpad into, dfault is one
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
    obj_func_dynamic_power = 100  # stress the importance of dynamic power and leakage power
    obj_func_leakage_power = 100
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

    cacti_exec_path = ("cacti")
    subprocess.call([cacti_exec_path,
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
                     str(ecc)])


if __name__ == '__main__':

    if len(sys.argv) < 5:
        print('Usage: <python_exec> cacti_wrapper.py tech_node size_in_bytes wordsize_in_bytes n_rw_ports n_banks')
        sys.exit(0)

    tech_node = sys.argv[1]
    size_in_bytes = sys.argv[2]
    wordsize_in_bytes = sys.argv[3]
    n_rw_ports = sys.argv[4]
    n_banks = sys.argv[5]

    cacti7_wrapper_for_SRAM(tech_node, size_in_bytes, wordsize_in_bytes, n_rw_ports, n_banks)
