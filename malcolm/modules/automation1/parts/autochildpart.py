from annotypes import add_call_types

from malcolm.core import PartRegistrar
from malcolm.modules import builtin, scanning

# 80 char line lengths...
AIV = builtin.parts.AInitialVisibility

APartName = builtin.parts.APartName
AMri = builtin.parts.AMri

class AutoChildPart(builtin.parts.ChildPart):
    def __init__(
        self, name: APartName, mri: AMri, initial_visibility: AIV = False
    ) -> None:
        super().__init__(name, mri, initial_visibility)

    def setup(self, registrar: PartRegistrar) -> None:
        super().setup(registrar)

        registrar.hook(
            (
                scanning.hooks.ConfigureHook,
                scanning.hooks.PostRunArmedHook,
                scanning.hooks.SeekHook,
            ),
            self.on_configure,
        )
        registrar.hook(scanning.hooks.RunHook, self.on_run)

    # noinspection PyPep8Naming
    @add_call_types
    def on_configure(
        self,
        context: scanning.hooks.AContext,
        completed_steps: scanning.hooks.ACompletedSteps,
        steps_to_do: scanning.hooks.AStepsToDo,
        axesToMove: scanning.hooks.AAxesToMove,
        generator: scanning.hooks.AGenerator,
    ) -> None:
        context.unsubscribe_all()
        child = context.block_view(self.mri)

        assert 'x' in axesToMove and 'y' in axesToMove, "TODO: Support different axes configurations"

        points = generator.get_points(completed_steps, completed_steps + steps_to_do)

        timeStep = points.duration[0]
        assert all(t == timeStep for t in points.duration), "TODO: Support time arrays"

        child.writeProfile(timeStep, points.positions['x'], points.positions['y'])


    @add_call_types
    def on_run(self, context: scanning.hooks.AContext) -> None:
        child = context.block_view(self.mri)
        child.executeProfile()
