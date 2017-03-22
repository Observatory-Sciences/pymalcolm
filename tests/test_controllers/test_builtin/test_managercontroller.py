import unittest
from mock import MagicMock

# module imports
from malcolm.compat import OrderedDict
from malcolm.controllers.builtin.managercontroller import ManagerController, \
    ManagerStates
from malcolm.core import Process, Part, Table
#from malcolm.parts.builtin.childpart import StatefulChildPart


class TestManagerStates(unittest.TestCase):

    def setUp(self):
        self.o = ManagerStates()

    def test_init(self):
        expected = OrderedDict()
        expected['Resetting'] = {'Ready', 'Fault', 'Disabling'}
        expected['Ready'] = {'Editing', "Fault", "Disabling", "Loading"}
        expected['Editing'] = {'Disabling', 'Editable', 'Fault'}
        expected['Editable'] = {'Fault', 'Saving', 'Disabling', 'Reverting'}
        expected['Saving'] = {'Fault', 'Ready', 'Disabling'}
        expected['Reverting'] = {'Fault', 'Ready', 'Disabling'}
        expected['Loading'] = {'Disabling', 'Fault', 'Ready'}
        expected['Fault'] = {"Resetting", "Disabling"}
        expected['Disabling'] = {"Disabled", "Fault"}
        expected['Disabled'] = {"Resetting"}
        assert self.o._allowed == expected


class TestManagerController(unittest.TestCase):
    maxDiff = None

    def checkState(self, state, child=True, parent=True):
        if child:
            self.assertEqual(self.c_child.state.value, state)
        if parent:
            self.assertEqual(self.c.state.value, state)

    def setUp(self):
        self.p = Process('process1', SyncFactory('threading'))

        # create a child ManagerController block
        params = ManagerController.MethodMeta. \
            prepare_input_map(mri='childBlock', configDir="/tmp")
        self.c_child = ManagerController(self.p, [], params)
        self.b_child = self.c_child.block

        self.sm = self.c_child.stateSet

        params = Part.MethodMeta.prepare_input_map(name='part1')
        part1 = Part(self.p, params)
        params = {'name': 'part2', 'mri': 'childBlock'}
        params = ChildPart.MethodMeta.prepare_input_map(**params)
        part2 = ChildPart(self.p, params)

        # create a root block for the ManagerController block to reside in
        parts = [part1, part2]
        params = ManagerController.MethodMeta.prepare_input_map(
            mri='mainBlock', configDir="/tmp")
        self.c = ManagerController(self.p, parts, params)
        self.b = self.c.block

        # check that do_initial_reset works asynchronously
        self.p.start()

        # wait until block is Ready
        task = Task("block_ready_task", self.p)
        task.when_matches(self.b["state"], self.sm.READY, timeout=1)

        self.checkState(self.sm.READY)

    def tearDown(self):
        self.p.stop()

    def test_init(self):

        # the following block attributes should be created by a call to
        # set_attributes via _set_block_children in __init__
        self.assertEqual(self.b['layout'].meta.typeid,
                         'malcolm:core/TableMeta:1.0')
        self.assertEqual(self.b['layoutName'].meta.typeid,
                         'malcolm:core/ChoiceMeta:1.0')

        # the following hooks should be created via _find_hooks in __init__
        self.assertEqual(self.c.hook_names, {
            self.c.Reset: "Reset",
            self.c.Disable: "Disable",
            self.c.Layout: "Layout",
            self.c.ReportPorts: "ReportPorts",
            self.c.Load: "Load",
            self.c.Save: "Save",
            self.c.ReportExportable: "ReportExportable",
        })

        # check instantiation of object tree via logger names
        self.assertEqual(self.c._logger.name,
                         'ManagerController(mainBlock)')
        self.assertEqual(self.c.parts['part1']._logger.name,
                         'ManagerController(mainBlock).part1')
        self.assertEqual(self.c.parts['part2']._logger.name,
                         'ManagerController(mainBlock).part2')
        self.assertEqual(self.c_child._logger.name,
                         'ManagerController(childBlock)')

    def test_edit(self):
        structure = MagicMock()
        self.c.load_structure = structure
        self.c.edit()
        # editing only affects one level
        self.checkState(self.sm.EDITABLE, child=False)
        self.assertEqual(self.c.load_structure, structure)

    def test_edit_exception(self):
        self.c.edit()
        with self.assertRaises(Exception):
            self.c.edit()

    def check_expected_save(self, x=0.0, y=0.0, visible="true"):
        expected = [x.strip() for x in ("""{
          "layout": {
            "part2": {
              "x": %s,
              "y": %s,
              "visible": %s
            }
          },
          "exports": {},
          "part2": {}
        }""" % (x, y, visible)).splitlines()]
        actual = [x.strip() for x in open(
            "/tmp/mainBlock/testSaveLayout.json").readlines()]
        self.assertEqual(actual, expected)

    def test_save(self):
        self.c.edit()
        params = {'layoutName': 'testSaveLayout'}
        params = ManagerController.save.MethodMeta.prepare_input_map(**params)
        self.c.save(params)
        self.check_expected_save()
        self.checkState(self.sm.AFTER_RESETTING, child=False)
        self.assertEqual(self.c.layout_name.value, 'testSaveLayout')
        os.remove("/tmp/mainBlock/testSaveLayout.json")
        self.c.edit()
        params = {'layoutName': None}
        params = ManagerController.save.MethodMeta.prepare_input_map(**params)
        self.c.save(params)
        self.check_expected_save()
        self.assertEqual(self.c.layout_name.value, 'testSaveLayout')

    def move_child_block(self):
        self.assertEqual(self.b.layout.x, [0])
        new_layout = Table(self.c.layout.meta)
        new_layout.name = ["part2"]
        new_layout.mri = ["P45-MRI"]
        new_layout.x = [10]
        new_layout.y = [20]
        new_layout.visible = [True]
        self.b.layout = new_layout
        self.assertEqual(self.b.layout.x, [10])

    def test_move_child_block_dict(self):
        self.b.edit()
        self.assertEqual(self.b.layout.x, [0])
        new_layout = dict(
            name=["part2"],
            mri=[""],
            x=[10],
            y=[20],
            visible=[True])
        self.b.layout = new_layout
        self.assertEqual(self.b.layout.x, [10])

    def test_revert(self):
        self.c.edit()
        self.move_child_block()
        self.assertEqual(self.b.layout.x, [10])
        self.c.revert()
        self.assertEqual(self.b.layout.x, [0])
        self.checkState(self.sm.AFTER_RESETTING, child=False)

    def test_set_and_load_layout(self):
        self.c.edit()
        self.checkState(self.sm.EDITABLE, child=False)

        new_layout = Table(self.c.layout.meta)
        new_layout.name = ["part2"]
        new_layout.mri = ["P45-MRI"]
        new_layout.x = [10]
        new_layout.y = [20]
        new_layout.visible = [False]
        self.b.layout = new_layout
        self.assertEqual(self.c.parts['part2'].x, 10)
        self.assertEqual(self.c.parts['part2'].y, 20)
        self.assertEqual(self.c.parts['part2'].visible, False)

        # save the layout, modify and restore it
        params = {'layoutName': 'testSaveLayout'}
        params = ManagerController.save.MethodMeta.prepare_input_map(**params)
        self.c.save(params)
        self.check_expected_save(10.0, 20.0, "false")

        self.c.parts['part2'].x = 30
        self.b.layoutName = 'testSaveLayout'
        self.assertEqual(self.c.parts['part2'].x, 10)

    def test_set_export_parts(self):
        self.assertEqual(list(self.b), [
            'meta',
            'state',
            'status',
            'busy',
            'layout',
            'layoutName',
            'exports',
            'disable',
            'edit',
            'reset',
            'revert',
            'save'])
        self.assertEqual(self.c.exports.meta.elements.name.choices, (
            'part2.busy',
            'part2.disable',
            'part2.edit',
            'part2.exports',
            'part2.layout',
            'part2.layoutName',
            'part2.reset',
            'part2.revert',
            'part2.save',
            'part2.state',
            'part2.status'))
        self.c.edit()
        new_exports = Table(self.c.exports.meta)
        new_exports.append(('part2.state', 'childState'))
        new_exports.append(('part2.edit', 'childEdit'))
        self.b.exports = new_exports
        params = {'layoutName': 'testSaveLayout'}
        params = ManagerController.save.MethodMeta.prepare_input_map(**params)
        self.c.save(params)
        self.assertEqual(list(self.b), [
            'meta',
            'state',
            'status',
            'busy',
            'layout',
            'layoutName',
            'exports',
            'disable',
            'edit',
            'reset',
            'revert',
            'save',
            'childState',
            'childEdit'])
        self.assertEqual(self.b.childState, self.sm.READY)
        #self.b.childEdit()
        #self.assertEqual(self.b.childState, self.ManagerStates.EDITABLE)



if __name__ == "__main__":
    unittest.main(verbosity=2)
