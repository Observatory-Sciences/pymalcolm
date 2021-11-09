import h5py
import os
from annotypes import add_call_types

from malcolm.core import PartRegistrar
from malcolm.modules import builtin, scanning

# 80 char line lengths...
AIV = builtin.parts.AInitialVisibility

APartName = builtin.parts.APartName
AMri = builtin.parts.AMri

POS_PATH = "/entry/{}.value"

class AutoChildPart(builtin.parts.ChildPart):
    def __init__(
        self, name: APartName, mri: AMri, initial_visibility: AIV = False
    ) -> None:
        super().__init__(name, mri, initial_visibility)

    def setup(self, registrar: PartRegistrar) -> None:
        super().setup(registrar)

        # TODO: Support pausing and resuming the scan
        registrar.hook(scanning.hooks.ConfigureHook, self.on_configure)
        registrar.hook(scanning.hooks.RunHook, self.on_run)
        registrar.hook(scanning.hooks.PostRunReadyHook, self.on_post_run)

        registrar.report(scanning.hooks.ConfigureHook.create_info(self.on_configure))

    # noinspection PyPep8Naming
    @add_call_types
    def on_configure(
        self,
        context: scanning.hooks.AContext,
        completed_steps: scanning.hooks.ACompletedSteps,
        steps_to_do: scanning.hooks.AStepsToDo,
        axesToMove: scanning.hooks.AAxesToMove,
        generator: scanning.hooks.AGenerator,
        fileDir: scanning.hooks.AFileDir,
        formatName: scanning.hooks.AFormatName = "det",
        fileTemplate: scanning.hooks.AFileTemplate = "%s.h5",
    ) -> None:
        child = context.block_view(self.mri)

        assert 'x' in axesToMove and 'y' in axesToMove, "TODO: Support different axes configurations"

        points = generator.get_points(completed_steps, completed_steps + steps_to_do)

        filename = fileTemplate % formatName
        self._filepath = os.path.join(fileDir, filename)

        timeStep = points.duration[0]
        assert all(t == timeStep for t in points.duration), "TODO: Support time arrays"

        child.writeProfile(timeStep, points.positions['x'], points.positions['y'])


    @add_call_types
    def on_run(self, context: scanning.hooks.AContext) -> None:
        child = context.block_view(self.mri)
        child.executeProfile()

    @add_call_types
    def on_post_run(self, context: scanning.hooks.AContext, **kwargs) -> None:
        child = context.block_view(self.mri)
        data = child.readbackPositions()

        # TODO: Arrange this data to match the scan specified by the scan generator
        # i.e. do what ADPosPlugin does
        with h5py.File(self._filepath, "w", libver="latest") as hdf:
            hdf.create_dataset(POS_PATH.format('x'), data=data.x)
            hdf.create_dataset(POS_PATH.format('y'), data=data.y)
