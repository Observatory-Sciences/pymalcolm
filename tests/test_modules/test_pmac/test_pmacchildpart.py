from os import environ

import numpy as np
import pytest
from mock import Mock, call, patch, ANY
from scanpointgenerator import LineGenerator, CompoundGenerator, \
    StaticPointGenerator

from malcolm.core import Context, Process
from malcolm.modules.pmac.parts import PmacChildPart
from malcolm.modules.scanning.infos import MotionTrigger, MotionTriggerInfo
from malcolm.testutil import ChildTestCase
from malcolm.yamlutil import make_block_creator


class TestPMACChildPart(ChildTestCase):
    def setUp(self):
        self.process = Process("Process")
        self.context = Context(self.process)
        pmac_block = make_block_creator(
            __file__, "test_pmac_manager_block.yaml")
        self.child = self.create_child_block(
            pmac_block, self.process, mri_prefix="PMAC",
            config_dir="/tmp")
        # These are the child blocks we are interested in
        self.child_x = self.process.get_controller("BL45P-ML-STAGE-01:X")
        self.child_y = self.process.get_controller("BL45P-ML-STAGE-01:Y")
        self.child_cs1 = self.process.get_controller("PMAC:CS1")
        self.child_traj = self.process.get_controller("PMAC:TRAJ")
        self.child_status = self.process.get_controller("PMAC:STATUS")
        # CS1 needs to have the right port otherwise we will error
        self.set_attributes(self.child_cs1, port="CS1")
        self.o = PmacChildPart(name="pmac", mri="PMAC")
        self.context.set_notify_dispatch_request(self.o.notify_dispatch_request)
        self.process.start()

    def tearDown(self):
        del self.context
        self.process.stop(timeout=1)

    # TODO: restore this tests when GDA does units right
    def _______________test_bad_units(self):
        with self.assertRaises(AssertionError) as cm:
            self.do_configure(["x", "y"], units="m")
        assert str(cm.exception) == "x: Expected scan units of 'm', got 'mm'"

    def resolutions_and_use_call(self, useB=True):
        return [
            call.put('useA', True),
            call.put('useB', useB),
            call.put('useC', False),
            call.put('useU', False),
            call.put('useV', False),
            call.put('useW', False),
            call.put('useX', False),
            call.put('useY', False),
            call.put('useZ', False)]

    def set_motor_attributes(
            self, x_pos=0.5, y_pos=0.0, units="mm",
            x_acceleration=2.5, y_acceleration=2.5,
            x_velocity=1.0, y_velocity=1.0):
        # create some parts to mock the motion controller and 2 axes in a CS
        self.set_attributes(
            self.child_x, cs="CS1,A",
            accelerationTime=x_velocity / x_acceleration, resolution=0.001,
            offset=0.0, maxVelocity=x_velocity, readback=x_pos,
            velocitySettle=0.0, units=units)
        self.set_attributes(
            self.child_y, cs="CS1,B",
            accelerationTime=y_velocity / y_acceleration, resolution=0.001,
            offset=0.0, maxVelocity=y_velocity, readback=y_pos,
            velocitySettle=0.0, units=units)

    def do_configure(self, axes_to_scan, completed_steps=0, x_pos=0.5,
                     y_pos=0.0, duration=1.0, units="mm", infos=None):
        self.set_motor_attributes(x_pos, y_pos, units)
        steps_to_do = 3 * len(axes_to_scan)
        xs = LineGenerator("x", "mm", 0.0, 0.5, 3, alternate=True)
        ys = LineGenerator("y", "mm", 0.0, 0.1, 2)
        generator = CompoundGenerator([ys, xs], [], [], duration)
        generator.prepare()
        self.o.configure(
            self.context, completed_steps, steps_to_do, {"part": infos},
            generator, axes_to_scan)

    def test_validate(self):
        generator = CompoundGenerator([], [], [], 0.0102)
        axesToMove = ["x"]
        # servoFrequency() return value
        self.child.handled_requests.post.return_value = 4919.300698316487
        ret = self.o.validate(self.context, generator, axesToMove, {})
        expected = 0.010166
        assert ret.value.duration == expected

    def do_check_output_quantized(self):
        assert self.child.handled_requests.mock_calls[:4] == [
            call.post('writeProfile', csPort='CS1', timeArray=[0.002],
                      userPrograms=[8]),
            call.post('executeProfile'),
            call.post('moveCS1', a=-0.1374875093687539, b=0.0,
                      moveTime=1.0374875094),
            call.post(
                'writeProfile',
                csPort='CS1',
                timeArray=pytest.approx(
                    [99950, 500250, 500250, 500250, 500250, 500250, 500250,
                     100000, 101000, 101000, 100000, 500250, 500250, 500250,
                     500250, 500250, 500250, 99950]),
                velocityMode=pytest.approx(
                    [1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 3]),
                userPrograms=pytest.approx(
                    [1, 4, 1, 4, 1, 4, 2, 8, 8, 8, 1, 4, 1, 4, 1, 4, 2, 8]),
                a=pytest.approx(
                    [-0.125, 0., 0.125, 0.25, 0.375, 0.5, 0.625, 0.63749375,
                     0.63749375, 0.63749375, 0.625, 0.5, 0.375, 0.25, 0.125, 0.,
                     -0.125, -0.13748751]),
                b=pytest.approx(
                    [0., 0., 0., 0., 0., 0., 0., 0.01237593, 0.05, 0.08762407,
                     0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1])
            )

        ]
        assert self.o.completed_steps_lookup == [
            0, 0, 1, 1, 2, 2, 3, 3, 3, 3,
            3, 3, 4, 4, 5, 5, 6, 6]

    def do_check_output(self, user_programs=None):
        if user_programs is None:
            user_programs = [
                1, 4, 1, 4, 1, 4, 2, 8, 8, 8, 1, 4, 1, 4, 1, 4, 2, 8
            ]
        # use a slice here because I'm getting calls to __str__ in debugger
        assert self.child.handled_requests.mock_calls[:4] == [
            call.post('writeProfile',
                      csPort='CS1', timeArray=[0.002], userPrograms=[8]),
            call.post('executeProfile'),
            call.post('moveCS1', a=-0.1375, b=0.0, moveTime=1.0375),
            # pytest.approx to allow sensible compare with numpy arrays
            call.post('writeProfile',
                      a=pytest.approx(
                          [-0.125, 0., 0.125, 0.25, 0.375, 0.5, 0.625, 0.6375,
                           0.6375, 0.6375, 0.625, 0.5, 0.375, 0.25, 0.125, 0.,
                           -0.125, -0.1375]),
                      b=pytest.approx(
                          [0., 0., 0., 0., 0., 0., 0., 0.0125, 0.05, 0.0875,
                           0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]),
                      csPort='CS1',
                      timeArray=pytest.approx(
                          [100000, 500000, 500000, 500000, 500000, 500000,
                           500000, 100000, 100000, 100000, 100000, 500000,
                           500000, 500000, 500000, 500000, 500000, 100000]),
                      userPrograms=pytest.approx(user_programs),
                      velocityMode=pytest.approx(
                          [1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0,
                           0, 0, 1, 3])
                      )
        ]
        assert self.o.completed_steps_lookup == [
            0, 0, 1, 1, 2, 2, 3, 3, 3, 3,
            3, 3, 4, 4, 5, 5, 6, 6]

    def do_check_output_slower(self):
        # use a slice here because I'm getting calls to __str__ in debugger
        assert self.child.handled_requests.mock_calls[:4] == [
            call.post('writeProfile', csPort='CS1', timeArray=[0.002],
                      userPrograms=[8]),
            call.post('executeProfile'),
            call.post('moveCS1', a=-0.1375, b=0.0, moveTime=1.0375),
            call.post('writeProfile',
                      a=pytest.approx(
                          [-0.125, 0., 0.125, 0.25, 0.375, 0.5, 0.625, 0.6375,
                           0.6375, 0.6375, 0.6375, 0.625, 0.5, 0.375, 0.25,
                           0.125, 0., -0.125, -0.1375]),
                      b=pytest.approx(
                          [0., 0., 0., 0., 0., 0., 0., 0.00125, 0.02, 0.08,
                           0.09875, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]),
                      csPort='CS1',
                      timeArray=pytest.approx(
                          [100000, 500000, 500000, 500000, 500000, 500000,
                           500000, 100000, 300000, 600000, 300000, 100000,
                           500000, 500000, 500000, 500000, 500000, 500000,
                           100000]),
                      userPrograms=pytest.approx(
                          [1, 4, 1, 4, 1, 4, 2, 8, 8, 8, 8, 1, 4, 1, 4, 1, 4,
                           2, 8]),
                      velocityMode=pytest.approx(
                          [1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1,
                           3])
                      )
        ]
        assert self.o.completed_steps_lookup == [
            0, 0, 1, 1, 2, 2, 3, 3, 3, 3, 3,
            3, 3, 4, 4, 5, 5, 6, 6]

    def do_check_sparse_output(self):
        assert self.child.handled_requests.mock_calls == [
            call.post('writeProfile',
                      csPort='CS1', timeArray=[0.002], userPrograms=[8]),
            call.post('executeProfile'),
            call.post('moveCS1', a=-0.1375, b=0.0, moveTime=1.0375),
            # pytest.approx to allow sensible compare with numpy arrays
            call.post(
                'writeProfile',
                a=pytest.approx([
                    -0.125, 0.625, 0.6375, 0.6375, 0.6375,
                    0.625, -0.125, -0.1375
                ]),
                b=pytest.approx([
                    0., 0., 0.0125, 0.05, 0.0875, 0.1, 0.1, 0.1
                ]),
                csPort='CS1',
                timeArray=pytest.approx([
                    100000, 3000000, 100000, 100000, 100000,
                    100000, 3000000, 100000
                ]),
                userPrograms=pytest.approx([1, 8, 0, 0, 0, 1, 8, 0]),
                velocityMode=pytest.approx([1, 1, 1, 1, 1, 1, 1, 3])
            )
        ]
        assert self.o.completed_steps_lookup == [0, 3, 3, 3, 3, 3, 6, 6]

    def test_configure(self):
        self.do_configure(axes_to_scan=["x", "y"])
        self.do_check_output()

    def test_configure_quantize(self):
        self.do_configure(axes_to_scan=["x", "y"], duration=1.0005)
        self.do_check_output_quantized()

    def test_configure_slower_vmax(self):
        self.set_attributes(self.child_y, maxVelocityPercent=10)
        self.do_configure(axes_to_scan=["x", "y"])
        self.do_check_output_slower()

    def test_configure_no_pulses(self):
        self.do_configure(axes_to_scan=["x", "y"],
                          infos=[MotionTriggerInfo(MotionTrigger.NONE)])
        self.do_check_output(user_programs=[0] * 18)

    def test_configure_start_of_row_pulses(self):
        self.do_configure(axes_to_scan=["x", "y"],
                          infos=[MotionTriggerInfo(MotionTrigger.ROW_GATE)])
        self.do_check_sparse_output()

    def test_configure_no_axes(self):
        self.set_motor_attributes()
        generator = CompoundGenerator(
            [StaticPointGenerator(6)], [], [], duration=0.1)
        generator.prepare()
        self.o.configure(self.context, 0, 6, {}, generator, [])
        assert self.child.handled_requests.mock_calls == [
            call.post('writeProfile',
                      csPort='CS1', timeArray=[0.002], userPrograms=[8]),
            call.post('executeProfile'),
            # pytest.approx to allow sensible compare with numpy arrays
            call.post('writeProfile',
                      csPort='CS1',
                      timeArray=pytest.approx([
                          2000, 50000, 50000, 50000, 50000, 50000, 50000,
                          50000, 50000, 50000, 50000, 50000, 50000, 2000]),
                      userPrograms=pytest.approx([
                          1, 4, 1, 4, 1, 4, 1, 4, 1, 4, 1, 4, 2, 8]),
                      velocityMode=pytest.approx([
                          1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 3]))
        ]
        assert self.o.completed_steps_lookup == [
            0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6]

    @patch("malcolm.modules.pmac.parts.pmacchildpart.PROFILE_POINTS", 4)
    def test_update_step(self):
        self.do_configure(axes_to_scan=["x", "y"], x_pos=0.0, y_pos=0.2)
        assert len(self.child.handled_requests.mock_calls) == 4
        # Check that the first trajectory moves to the first place
        positionsA = self.child.handled_requests.post.call_args_list[-1][1]["a"]
        assert len(positionsA) == 4
        assert positionsA[-1] == 0.25
        assert self.o.end_index == 2
        assert len(self.o.completed_steps_lookup) == 5
        assert len(self.o.profile["timeArray"]) == 1
        self.o.registrar = Mock()
        self.child.handled_requests.reset_mock()
        self.o.update_step(
            3, self.context.block_view("PMAC"))
        self.o.registrar.report.assert_called_once()
        assert self.o.registrar.report.call_args[0][0].steps == 1
        assert not self.o.loading
        assert self.child.handled_requests.mock_calls == [
            # pytest.approx to allow sensible compare with numpy arrays
            call.post('writeProfile',
                      a=pytest.approx([0.375, 0.5, 0.625, 0.6375]),
                      b=pytest.approx([0.0, 0.0, 0.0, 0.0125]),
                      timeArray=pytest.approx([
                          500000, 500000, 500000, 100000]),
                      userPrograms=pytest.approx([1, 4, 2, 8]),
                      velocityMode=pytest.approx([0, 0, 1, 1])
                      )
        ]
        assert self.o.end_index == 3
        assert len(self.o.completed_steps_lookup) == 11
        assert len(self.o.profile["timeArray"]) == 3

    def test_run(self):
        self.o.generator = ANY
        self.o.run(self.context)
        assert self.child.handled_requests.mock_calls == [
            call.post('executeProfile')]

    def test_reset(self):
        self.o.generator = ANY
        self.o.reset(self.context)
        assert self.child.handled_requests.mock_calls == [
            call.post('abortProfile')]

    def test_multi_run(self):
        self.do_configure(axes_to_scan=["x"])
        assert self.o.completed_steps_lookup == (
            [0, 0, 1, 1, 2, 2, 3, 3])
        self.child.handled_requests.reset_mock()
        self.do_configure(
            axes_to_scan=["x"], completed_steps=3, x_pos=0.6375)
        assert self.child.handled_requests.mock_calls == [
            call.post('writeProfile', csPort='CS1', timeArray=[0.002],
                      userPrograms=[8]),
            call.post('executeProfile'),
            call.post('moveCS1', a=0.6375, moveTime=0.0),
            call.post(
                'writeProfile',
                csPort='CS1',
                a=pytest.approx([
                    0.625, 0.5, 0.375, 0.25, 0.125, 0.0, -0.125, -0.1375]),
                timeArray=pytest.approx([
                    100000, 500000, 500000, 500000, 500000, 500000, 500000,
                    100000]),
                userPrograms=pytest.approx([1, 4, 1, 4, 1, 4, 2, 8]),
                velocityMode=pytest.approx([1, 0, 0, 0, 0, 0, 1, 3])),
        ]

    def test_long_steps_lookup(self):
        self.do_configure(
            axes_to_scan=["x"], completed_steps=3, x_pos=0.62506, duration=14.0)
        # Ignore the trigger reset and move to start, just look at the last call
        # which is the profile write
        assert self.child.handled_requests.mock_calls[-1] == call.post(
            'writeProfile',
            csPort='CS1',
            a=pytest.approx([
                0.625, 0.5625, 0.5, 0.4375, 0.375, 0.3125, 0.25, 0.1875,
                0.125, 0.0625, 0.0, -0.0625, -0.125, -0.12506377551020409]),
            timeArray=pytest.approx([
                7143, 3500000, 3500000, 3500000, 3500000, 3500000, 3500000,
                3500000, 3500000, 3500000, 3500000, 3500000, 3500000, 7143]),
            userPrograms=pytest.approx([
                1, 0, 4, 0, 1, 0, 4, 0, 1, 0, 4, 0, 2, 8]),
            velocityMode=pytest.approx([
                1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 3]))
        assert self.o.completed_steps_lookup == (
            [3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6])

    @patch("malcolm.modules.pmac.parts.pmacchildpart.PROFILE_POINTS", 9)
    def test_split_in_a_long_step_lookup(self):
        self.do_configure(
            axes_to_scan=["x"], completed_steps=3, x_pos=0.62506,
            duration=14.0)
        # Ignore the trigger reset and move to start, just look at the last call
        # which is the profile write
        assert self.child.handled_requests.mock_calls[-1] == call.post(
            'writeProfile',
            csPort='CS1',
            a=pytest.approx([
                0.625, 0.5625, 0.5, 0.4375, 0.375, 0.3125, 0.25, 0.1875,
                0.125]),
            timeArray=pytest.approx([
                7143, 3500000, 3500000, 3500000, 3500000, 3500000, 3500000,
                3500000, 3500000]),
            userPrograms=pytest.approx([
                1, 0, 4, 0, 1, 0, 4, 0, 1]),
            velocityMode=pytest.approx([
                1, 0, 0, 0, 0, 0, 0, 0, 0]))
        # The completed steps works on complete (not split) steps, so we expect
        # the last value to be the end of step 6, even though it doesn't
        # actually appear in the velocity arrays
        assert self.o.completed_steps_lookup == (
            [3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6])
        # Mock out the registrar that would have been registered when we
        # attached to a controller
        self.o.registrar = Mock()
        # Now call update step and get it to generate the next lot of points
        # scanned can be any index into completed_steps_lookup so that there
        # are less than PROFILE_POINTS left to go in it
        self.o.update_step(
            scanned=2, child=self.process.block_view("PMAC"))
        # Expect the rest of the points
        assert self.child.handled_requests.mock_calls[-1] == call.post(
            'writeProfile',
            a=pytest.approx([
                0.0625, 0.0, -0.0625, -0.125, -0.12506377551020409]),
            timeArray=pytest.approx([
                3500000, 3500000, 3500000, 3500000, 7143]),
            userPrograms=pytest.approx([
                0, 4, 0, 2, 8]),
            velocityMode=pytest.approx([
                0, 0, 0, 1, 3]))
        assert self.o.registrar.report.call_count == 1
        assert self.o.registrar.report.call_args[0][0].steps == 3
        # And for the rest of the lookup table to be added
        assert self.o.completed_steps_lookup == (
            [3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6])

    def do_2d_trajectory_with_plot(self, gen, xv, yv, xa, ya, title):
        gen.prepare()

        self.set_motor_attributes(
            x_acceleration=xv / xa, y_acceleration=yv / ya,
            x_velocity=xv, y_velocity=yv)

        infos = [MotionTriggerInfo(MotionTrigger.ROW_GATE)]
        # infos = [MotionTriggerInfo(MotionTrigger.EVERY_POINT)]
        self.o.configure(self.context, 0, gen.size,
                         {"part": infos},
                         gen, ["x", "y"])

        name, args, kwargs = self.child.handled_requests.mock_calls[2]
        assert name == "post"
        assert args[0] == "moveCS1"
        # add in the start point to the position and time arrays
        xp = np.array([kwargs['a']])
        yp = np.array([kwargs['b']])
        tp = np.array([0])
        # And the profile write
        name, args, kwargs = self.child.handled_requests.mock_calls[-1]
        assert name == "post"
        assert args[0] == "writeProfile"
        xp = np.append(xp, kwargs["a"])
        yp = np.append(yp, kwargs["b"])
        tp = np.append(tp, kwargs["timeArray"])

        # if this test is run in pycharm then it plots some results
        # to help diagnose issues
        if environ.get("PLOTS") == '1':
            import matplotlib.pyplot as plt

            times = np.cumsum(tp / 1000)  # show in millisecs

            fig1 = plt.figure(figsize=(8, 6), dpi=300)
            plt.title("{} x/time {} points".format(title, xp.size))
            plt.plot(xp, times, '+', ms=2.5)
            fig2 = plt.figure(figsize=(8, 6), dpi=300)
            plt.title("{} x/y".format(title))
            plt.plot(xp, yp, '+', ms=2.5)
            plt.show()

        return xp, yp

    def check_bounds(self, a, name):
        # tiny amounts of overshoot are acceptable
        npa = np.array(a)
        less_start = np.argmax((npa[0] - npa) > 0.000001)
        greater_end = np.argmax((npa - npa[-1]) > 0.000001)
        self.assertEqual(
            less_start, 0, "Position {} < start for {}\n{}".format(
                less_start, name, a))
        self.assertEqual(
            greater_end, 0, "Position {} > end for {}\n{}".format(
                greater_end, name, a))

    def test_turnaround_overshoot(self):
        """ check for a previous bug in a sawtooth X,Y scan
        The issue was that the first point at the start of each rising edge
        overshot in Y. The parameters for each rising edge are below.

        Line Y, start=-2.5, stop= -2.5 +0.025, points=30
        Line X, start=-0.95, stop= -0.95 +0.025, points=30
        duration=0.15

        X motor: VMAX=17, ACCL=0.1 (time to VMAX)
        Y motor: VMAX=1, ACCL=0.2
        """
        xs = LineGenerator("x", "mm", -2.5, -2.475, 30)
        ys = LineGenerator("y", "mm", -.95, -.925, 2)

        generator = CompoundGenerator([ys, xs], [], [], 0.15)

        x1, y1 = self.do_2d_trajectory_with_plot(
            generator, xv=17, yv=1, xa=.1, ya=.2,
            title='test_turnaround_overshoot 10 fast')
        self.child.handled_requests.reset_mock()

        x2, y2 = self.do_2d_trajectory_with_plot(
            generator, xv=17, yv=34, xa=10, ya=.1,
            title='test_turnaround_overshoot 10 slower')
        self.child.handled_requests.reset_mock()

        # check all the points in the arrays are within their start and stop
        self.check_bounds(x1, "x1")
        self.check_bounds(x2, "x2")
        self.check_bounds(y1, "y1")
        self.check_bounds(y2, "y2")
