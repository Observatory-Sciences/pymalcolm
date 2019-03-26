from annotypes import Anno, Array, Union, Sequence, Any, Serializable
from enum import Enum
from scanpointgenerator import CompoundGenerator
import numpy as np

from malcolm.core import VMeta, NTUnion, Table, NumberMeta, Widget, \
    config_tag, Display, AttributeModel
from malcolm.modules.builtin.util import ManagerStates

with Anno("Generator instance providing specification for scan"):
    AGenerator = CompoundGenerator
with Anno("List of axes in inner dimension of generator that should be moved"):
    AAxesToMove = Array[str]
UAxesToMove = Union[AAxesToMove, Sequence[str]]
with Anno("Directory to write data to"):
    AFileDir = str
with Anno("Argument for fileTemplate, normally filename without extension"):
    AFormatName = str
with Anno("""Printf style template to generate filename relative to fileDir.
Arguments are:
  1) %s: the value of formatName"""):
    AFileTemplate = str
with Anno("The demand exposure time of this scan, 0 for the maximum possible"):
    AExposure = float


def exposure_attribute(min_exposure):
    # type: (float) -> AttributeModel
    meta = NumberMeta(
        "float64", "The calculated exposure for this run",
        tags=[Widget.TEXTUPDATE.tag(), config_tag()],
        display=Display(precision=6, units="s", limitLow=min_exposure)
    )
    return meta.create_attribute_model()


class ConfigureParams(Serializable):
    # This will be serialized, so maintain camelCase for axesToMove
    # noinspection PyPep8Naming
    def __init__(self, generator, axesToMove=None, **kwargs):
        # type: (AGenerator, UAxesToMove, **Any) -> None
        if kwargs:
            # Got some additional args to report
            self.call_types = self.call_types.copy()
            for k in kwargs:
                # We don't use this apart from its presence,
                # so no need to fill in description, typ, etc.
                self.call_types[k] = Anno("")
            self.__dict__.update(kwargs)
        self.generator = generator
        if axesToMove is None:
            axesToMove = generator.axes
        self.axesToMove = AAxesToMove(axesToMove)


class RunnableStates(ManagerStates):
    CONFIGURING = "Configuring"
    ARMED = "Armed"
    RUNNING = "Running"
    POSTRUN = "PostRun"
    PAUSED = "Paused"
    SEEKING = "Seeking"
    ABORTING = "Aborting"
    ABORTED = "Aborted"

    def create_block_transitions(self):
        super(RunnableStates, self).create_block_transitions()
        # Set transitions for normal states
        self.set_allowed(self.READY, self.CONFIGURING)
        self.set_allowed(self.CONFIGURING, self.ARMED)
        self.set_allowed(self.ARMED,
                         self.RUNNING, self.SEEKING, self.RESETTING)
        self.set_allowed(self.RUNNING, self.POSTRUN, self.SEEKING)
        self.set_allowed(self.POSTRUN, self.READY, self.ARMED)
        self.set_allowed(self.SEEKING, self.ARMED, self.PAUSED)
        self.set_allowed(self.PAUSED, self.SEEKING, self.RUNNING)

        # Add Abort to all normal states
        normal_states = [
            self.READY, self.CONFIGURING, self.ARMED, self.RUNNING,
            self.POSTRUN, self.PAUSED, self.SEEKING]
        for state in normal_states:
            self.set_allowed(state, self.ABORTING)

        # Set transitions for aborted states
        self.set_allowed(self.ABORTING, self.ABORTED)
        self.set_allowed(self.ABORTED, self.RESETTING)


@Serializable.register_subclass("malcolm:core/PointGeneratorMeta:1.0")
@VMeta.register_annotype_converter(CompoundGenerator)
class PointGeneratorMeta(VMeta):

    attribute_class = NTUnion

    def doc_type_string(self):
        return "CompoundGenerator"

    def default_widget(self):
        return Widget.TREE

    def validate(self, value):
        if value is None:
            return CompoundGenerator([], [], [])
        elif isinstance(value, CompoundGenerator):
            return value
        elif isinstance(value, dict):
            # Sanitise the dict in place
            # TODO: remove this when scanpoint generator supports ndarray inputs
            def sanitize(d):
                for k, v in d.items():
                    if isinstance(v, np.ndarray):
                        d[k] = list(v)
                    elif isinstance(v, list):
                        for x in v:
                            if isinstance(x, dict):
                                sanitize(x)
                    elif isinstance(v, dict):
                        sanitize(v)
            sanitize(value)
            return CompoundGenerator.from_dict(value)
        else:
            raise TypeError(
                "Value %s must be a Generator object or dictionary" % value)


class DatasetType(Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    MONITOR = "monitor"
    POSITION_SET = "position_set"
    POSITION_VALUE = "position_value"


with Anno("Dataset names"):
    ADatasetNames = Array[str]
with Anno("Filenames of HDF files relative to fileDir"):
    AFilenames = Array[str]
with Anno("Types of dataset"):
    ADatasetTypes = Array[DatasetType]
with Anno("Rank (number of dimensions) of the dataset"):
    ARanks = Array[np.int32]
with Anno("Dataset paths within HDF files"):
    APaths = Array[str]
with Anno("UniqueID array paths within HDF files"):
    AUniqueIDs = Array[str]
UDatasetNames = Union[ADatasetNames, Sequence[str]]
UFilenames = Union[AFilenames, Sequence[str]]
UDatasetTypes = Union[ADatasetTypes, Sequence[DatasetType]]
URanks = Union[ARanks, Sequence[np.int32]]
UPaths = Union[APaths, Sequence[str]]
UUniqueIDs = Union[AUniqueIDs, Sequence[str]]


class DatasetTable(Table):
    # This will be serialized so we need type to be called type
    # noinspection PyShadowingBuiltins
    def __init__(self,
                 name,  # type: UDatasetNames
                 filename,  # type: UFilenames
                 type,  # type: UDatasetTypes
                 rank,  # type: URanks
                 path,  # type: UPaths
                 uniqueid,  # type: UUniqueIDs
                 ):
        # type: (...) -> None
        self.name = ADatasetNames(name)
        self.filename = AFilenames(filename)
        self.type = ADatasetTypes(type)
        self.rank = ARanks(rank)
        self.path = APaths(path)
        self.uniqueid = AUniqueIDs(uniqueid)


with Anno("Detector names"):
    ADetectorNames = Array[str]
with Anno("Detector block mris"):
    ADetectorMris = Array[str]
with Anno("Exposure of each detector frame for the current scan"):
    AExposures = Array[float]
with Anno("Number of detector frames for each generator point"):
    AFramesPerPoints = Array[np.int32]
UDetectorNames = Union[ADetectorNames, Sequence[str]]
UDetectorMris = Union[ADetectorMris, Sequence[str]]
UExposures = Union[AExposures, Sequence[float]]
UFramesPerPoints = Union[AFramesPerPoints, Sequence[np.int32]]


class DetectorTable(Table):
    # Will be serialized so use camelCase
    # noinspection PyPep8Naming
    def __init__(self,
                 name,  # type: UDetectorNames
                 mri,  # type: UDetectorMris
                 exposure,  # type: UExposures
                 framesPerPoint,  # type: UFramesPerPoints
                 ):
        # type: (...) -> None
        self.name = ADetectorNames(name)
        self.mri = ADetectorMris(mri)
        self.exposure = AExposures(exposure)
        self.framesPerPoint = AFramesPerPoints(framesPerPoint)