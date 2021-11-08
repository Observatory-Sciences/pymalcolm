from malcolm.yamlutil import check_yaml_names, make_include_creator

motor_records = make_include_creator(__file__, "motor_records.yaml")
profile_move_axis_records = make_include_creator(__file__, "profile_move_axis_records.yaml")
profile_move_controller_records = make_include_creator(__file__, "profile_move_controller_records.yaml")
rawmotor_collection = make_include_creator(__file__, "rawmotor_collection.yaml")
auto_trajectory_collection = make_include_creator(__file__, "auto_trajectory_collection.yaml")

__all__ = check_yaml_names(globals())
