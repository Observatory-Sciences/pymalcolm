from malcolm.yamlutil import check_yaml_names, make_block_creator

raw_motor_block = make_block_creator(__file__, "raw_motor_block.yaml")
auto_trajectory_block = make_block_creator(__file__, "auto_trajectory_block.yaml")

__all__ = check_yaml_names(globals())
