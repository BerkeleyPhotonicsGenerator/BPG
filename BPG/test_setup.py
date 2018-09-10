import BPG


def bpg_setup():
    """ Creates the BAG project instance to be used """
    # TODO: Convert to a pytest fixture
    local_dict = locals()
    if 'prj' not in local_dict:
        print('creating BAG project')
        bprj = BPG.PhotonicBagProject()
    else:
        print('loading BAG project')
        bprj = local_dict['bprj']
    return bprj
