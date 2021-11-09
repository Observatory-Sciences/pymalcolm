import numpy as np

from annotypes import Anno, Union, Array, Sequence, add_call_types

from malcolm.modules import builtin, scanning
from malcolm.core import PartRegistrar, Table

APartName = builtin.parts.APartName
AMri = builtin.parts.AMri

with Anno("The position the axis should be at for each point in the scan"):
    ADemandTrajectory = Array[np.float64]
with Anno("The fixed timestep between points"):
    ATimeStep = np.float64
with Anno("A position array"):
    APosArray = Union[Array[float]]

UPosArray = Union[APosArray, Sequence[float]]

class PositionTable(Table):
    def __init__(self, x: UPosArray, y: UPosArray):
        self.x = APosArray(x)
        self.y = APosArray(y)

with Anno("The readback positions"):
    APosTable = PositionTable


class AutoTrajectoryPart(builtin.parts.ChildPart):
    def __init__(
        self,
        name: APartName,
        mri: AMri,
    ) -> None:
        super().__init__(name, mri, initial_visibility=True)
        self.total_time = 0

    def setup(self, registrar: PartRegistrar) -> None:
        super().setup(registrar)

        registrar.add_method_model(
            self.write_profile, "writeProfile", needs_context=True,
        )
        registrar.add_method_model(
            self.execute_profile, "executeProfile", needs_context=True
        )
        registrar.add_method_model(
            self.readback_positions, "readbackPositions", needs_context=True
        )
        registrar.add_method_model(
            self.abort_profile, "abortProfile", needs_context=True
        )

    @add_call_types
    def write_profile(
        self,
        context: builtin.hooks.AContext, 
        timeStep: ATimeStep,
        x: ADemandTrajectory,
        y: ADemandTrajectory,
    ) -> None:
        child = context.block_view(self.mri)

        assert len(x) == len(y), "Trajectories must have the same length"

        numPoints = len(x)
        self.total_time = numPoints * timeStep;

        child.put_attribute_values({
            'numAxes': 2,
            'numPoints': numPoints,
            'fixedTime': timeStep,
            'xPositions': x,
            'useXAxis': True,
            'yPositions': y,
            'useYAxis': True,
        })

        child.buildProfile()

    @add_call_types
    def execute_profile(self, context: builtin.hooks.AContext) -> None:
        child = context.block_view(self.mri)

        child.executeProfile()

        # TODO(tri): How do we determine if the scan has finished?
        context.sleep(self.total_time)

    @add_call_types
    def readback_positions(self, context: builtin.hooks.AContext) -> APosTable:
        child = context.block_view(self.mri)

        child.readbackPositions()

        return PositionTable(child.xReadbacks.value, child.yReadbacks.value)

    @add_call_types
    def abort_profile(self, context: builtin.hooks.AContext) -> None:
        child = context.block_view(self.mri)

        assert false, "TODO"
