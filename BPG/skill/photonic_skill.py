
from bag.interface.skill import *


class PhotonicSkillInterface(SkillInterface):
    def __init__(self, dealer, tmp_dir, db_config):
        SkillInterface.__init__(self, dealer, tmp_dir, db_config)

    def create_global_skill_variables(self,
                                      dataprep_procedure_path,
                                      dataprep_parameters_path,
                                      output_file_path,
                                      ):
        """

        Parameters
        ----------
        dataprep_procedure_path
        dataprep_parameters_path
        output_file_path

        Returns
        -------

        """
        # Initialize empty list to stream out
        outlines = list()

        # List of required parameters for SKILL dataprep functions
        required_params = ['GlobalGridSize', 'GlobalRoughGridSize', 'GlobalNumVertices', 'GlobalSubPolygonXPitch']

        with open(dataprep_procedure_path, 'r') as f:
            dataprep_routine_specs = yaml.load(f, Loader=yaml.CFullLoader if yaml.__with_libyaml__ else yaml.FullLoader)

        # Check that required dataprep parameters exist
        for param in required_params:
            if param in dataprep_routine_specs:
                outlines.append("{param} = {value}\n".format(
                    param=param, value=dataprep_routine_specs[param])
                )
            else:
                raise ValueError(
                    "Parameter '{param}' must be specified in dataprep_routine.yaml for skill based dataprep "
                    "to work".format(param=param))

        # Write out the dataprep layout parameters
        outlines.append("\n\n\n")
        with open(dataprep_parameters_path, 'r') as f:
            dataprep_params = yaml.load(f, Loader=yaml.CFullLoader if yaml.__with_libyaml__ else yaml.FullLoader)

        outlines.extend(self._dataprep_params_dict_to_skill_function(dataprep_params))
        outlines.append("\n\n\n")

        # Write the dataprep operation groups
        if 'dataprep_groups' not in dataprep_routine_specs:
            raise ValueError("Parameter 'dataprep_groups' must be specified in dataprep_routine.yaml for skill based "
                             "dataprep to work")
        if 'over_under_under_over' not in dataprep_routine_specs:
            raise ValueError(
                "Parameter 'over_under_under_over' must be specified in dataprep_routine.yaml for skill based "
                "dataprep to work")
        outlines.extend(self._dataprep_groups_list_to_skill_list(
            dataprep_routine_specs['dataprep_groups'],
            dataprep_routine_specs['over_under_under_over']
        ))
        outlines.append("\n\n\n")

        with open(output_file_path, 'w') as stream:
            stream.writelines(outlines)

    def _dataprep_groups_list_to_skill_list(self,
                                            dataprep_operation_list,
                                            dataprep_ouo_list,
                                            ):
        """
        Convert the given dataprep operations list (from dataprep_routine.yaml) into the SKILL list format

        Parameters
        ----------
        dataprep_operation_list :
        dataprep_ouo_list

        Returns
        -------

        """

        outlines = list()
        outlines.append("GlobalDataPrepGroups = \n")
        outlines.append("list(\n")
        for dataprep_group in dataprep_operation_list:
            # Start the dataprep group
            outlines.append("    list(\n")
            # Start the lpp_in group
            outlines.append("        list(\n")

            for lpp_in in dataprep_group['lpp_in']:
                outlines.append("            list(\"{layer}\" \"{purpose}\")\n".format(
                    layer=lpp_in[0], purpose=lpp_in[1])
                )

            outlines.append("        ) ; end lpp_in list\n")
            outlines.append("        list(\n")

            for lpp_op in dataprep_group['lpp_ops']:
                outlines.append("            list(    list(\"{layer}\" \"{purpose}\")  \"{op}\" {amount})\n".format(
                    layer=lpp_op[0], purpose=lpp_op[1], op=lpp_op[2], amount=lpp_op[3])
                )

            outlines.append("        ) ; end lpp_op list\n")
            outlines.append("    ) ; end dataprep operation group\n")

        outlines.extend(self._dataprep_ouo_list_to_skill_list(dataprep_ouo_list))
        outlines.append(") ; end GlobalDataPrepGroups\n")

        return outlines

    @staticmethod
    def _dataprep_ouo_list_to_skill_list(dataprep_ouo_list):
        """
        Convert the given dataprep ouo list (from dataprep_routine.yaml) into the SKILL list format

        Parameters
        ----------
        dataprep_ouo_list :

        Returns
        -------

        """

        outlines = list()
        # Start the dataprep group
        outlines.append("    ; OUO dataprep group\n")
        outlines.append("    list(\n")
        outlines.append("        ; OUO list\n")
        outlines.append("        list(\n")
        for ouo_layer in dataprep_ouo_list:
            # Start the dataprep group
            outlines.append("            list(\"{layer}\" \"{purpose}\") \n".format(
                layer=ouo_layer[0], purpose=ouo_layer[1])
            )
        outlines.append("        ) ; end OUO list\n")
        outlines.append("        list(\n")
        outlines.append("            list( nil  \"ouo\" nil)\n")
        outlines.append("        ) ; end lpp_op list\n")
        outlines.append("    ) ; end ouo dataprep group\n")

        return outlines

    @staticmethod
    def _dataprep_params_dict_to_skill_function(dataprep_params):
        """
        Convert the given dataprep parameters (from dataprep_parameters.yaml) into the SKILL procedure

        Parameters
        ----------
        dataprep_params

        Returns
        -------

        """

        outlines = list()
        outlines.append("procedure( GlobalGR(rule layer @optional (layeroptional \"none\"))\n")
        outlines.append("    let( (out)\n")
        outlines.append("        case( rule\n")
        for rule_key, layer_dicts in dataprep_params.items():
            outlines.append("            (\"{rule_key}\" case( layer\n".format(rule_key=rule_key))
            for layer_name, layer_value in layer_dicts.items():
                outlines.append("                (\"{layer}\"  out = {value} )\n".format(
                    layer=layer_name, value=layer_value)
                )
            outlines.append("                ( t  out = 0);nil)\n")  # default value if layer is not valid
            outlines.append("            ) ; end of the layer switch\n")
            outlines.append("            ) ; end of rule {rule_key}\n".format(rule_key=rule_key))
        outlines.append("            ( t  out = nil)\n")
        outlines.append("        )\n")
        outlines.append("        out\n")
        outlines.append("    ) ; end of let\n")
        outlines.append(") ; end of procedure\n")

        return outlines

    def setup_bpg_skill(self,
                        output_path,
                        dataprep_procedure_path,
                        dataprep_parameters_path,
                        dataprep_skill_function_path,
                        ):
        """

        Parameters
        ----------
        output_path
        dataprep_procedure_path
        dataprep_parameters_path
        dataprep_skill_function_path

        Returns
        -------

        """

        # Load the skill dataprep functions
        cmd = 'load("{}")'.format(dataprep_skill_function_path)
        self._eval_skill(cmd)

        file_path = os.path.join(output_path, 'dataprep_skill_params.il')
        self.create_global_skill_variables(dataprep_procedure_path,
                                           dataprep_parameters_path,
                                           output_file_path=file_path
                                           )

        cmd = 'load("{}")'.format(file_path)
        self._eval_skill(cmd)

    def dataprep(self,
                 lib_name,
                 cell_name,
                 debug=False
                 ):

        if debug:
            debug_txt = "'t"
        else:
            debug_txt = "nil"

        cmd = 'DataPrepWrapper( "{lib_name}" "{cell_name}" {debug} )'.format(
            lib_name=lib_name, cell_name=cell_name, debug=debug_txt
        )
        self._eval_skill(cmd)

    def manh(self,
             lib_name,
             cell_name,
             debug=False
             ):

        if debug:
            debug_txt = "'t"
        else:
            debug_txt = "nil"

        cmd = 'ManhCell( "{lib_name}" "{cell_name}" {debug} )'.format(
            lib_name=lib_name, cell_name=cell_name, debug=debug_txt
        )
        self._eval_skill(cmd)
