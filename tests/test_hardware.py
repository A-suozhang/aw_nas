import pytest

import torch

@pytest.mark.parametrize(
    "case",
    [
        {
            "genotypes": [
                {
                    "prim_type": "mobilenet_v2_block",
                    "C": 16,
                    "C_out": 24,
                    "spatial_size": 112,
                    "expansion": 6,
                    "stride": 2,
                    "kernel_size": 3,
                },
                {
                    "prim_type": "mobilenet_v2_block",
                    "C": 24,
                    "C_out": 24,
                    "spatial_size": 56,
                    "expansion": 3,
                    "stride": 1,
                    "kernel_size": 5,
                }
            ],
            "arch": [
                {
                    "prim_type": "mobilenet_v2_block",
                    "C": 16,
                    "C_out": 24,
                    "spatial_size": 112,
                    "expansion": 6,
                    "stride": 2,
                    "kernel_size": 3,
                },
                {
                    "prim_type": "mobilenet_v2_block",
                    "C": 24,
                    "C_out": 24,
                    "spatial_size": 56,
                    "expansion": 3,
                    "stride": 1,
                    "kernel_size": 5,
                }
            ],
        },
        {
            "genotypes": '[{"prim_type": "mobilenet_v3_block", "C": 16,"C_out": 24, "spatial_size": 112, "expansion": 4, "use_se": True, "stride": 2, "kernel_size": 3, "activation": "relu"}]',
            "arch": [
                {
                    "prim_type": "mobilenet_v3_block",
                    "C": 16,
                    "C_out": 24,
                    "spatial_size": 112,
                    "expansion": 4,
                    "use_se": True,
                    "stride": 2,
                    "kernel_size": 3,
                    "activation": "relu",
                }
            ],
        },
    ],
)
def test_general_rollout(case):
    from aw_nas.common import get_search_space
    from aw_nas.final.general_model import GeneralGenotypeModel
    from aw_nas.utils.elapse_utils import analyze_elapses

    ss = get_search_space("general", primitives=[])
    genotype = ss.genotype(case["arch"])
    rollout = ss.rollout_from_genotype(genotype)
    assert genotype == ss.genotype(rollout.genotype_list())
    assert rollout == ss.rollout_from_genotype(case["genotypes"])

    model = GeneralGenotypeModel(ss, "cuda", genotype)

    inputs = torch.rand([1, case["arch"][0]["C"], case["arch"][0]["spatial_size"],
                         case["arch"][0]["spatial_size"]])
    gpu_performance = analyze_elapses(model, inputs.cuda(), use_cuda=True, forward_time=1)
    for prim in gpu_performance["primitives"]:
        print(prim["elapse"])
        assert prim["elapse"] > 0
    print("GPU elapse: ", gpu_performance["async_elapse"], gpu_performance["sync_elapse"])
    assert gpu_performance["async_elapse"] < gpu_performance["sync_elapse"]

    model = model.to("cpu")
    cpu_performance = analyze_elapses(model, inputs.cpu(), use_cuda=False, forward_time=1)
    for prim in cpu_performance["primitives"]:
        assert prim["elapse"] > 0
    print("CPU elapse: ", cpu_performance["async_elapse"], cpu_performance["sync_elapse"])


@pytest.mark.parametrize(
    "case",
    [
        {
            "search_space_cfg": {
                "width_choice": [3, 4, 6],
                "depth_choice": [2, 3, 4],
                "kernel_choice": [3, 5, 7],
                "num_cell_groups": [1, 4, 4, 4, 4, 4],
                "expansions": [1, 6, 6, 6, 6, 6],
            },
            "prof_prim_cfg": {
                "spatial_size": 112,
                "base_channels": [16, 16, 24, 32, 64, 96, 160, 320, 1280],
                "mult_ratio": 1.0,
                "strides": [1, 2, 2, 2, 1, 2],
                "activation": ["relu", "relu", "relu", "h_swish", "h_swish", "h_swish"],
                "use_se": [False, False, True, False, True, True],
                "primitive_type": "mobilenet_v3_block",
            },
        }
    ],
)
def test_genprof(case):
    from aw_nas.common import get_search_space, genotype_from_str
    from aw_nas.hardware.base import MixinProfilingSearchSpace
    from aw_nas.hardware.utils import Prim, assemble_profiling_nets
    from aw_nas.rollout.general import GeneralSearchSpace

    ss = get_search_space("ofa_mixin", **case["search_space_cfg"])
    assert isinstance(ss, MixinProfilingSearchSpace)
    primitives = ss.generate_profiling_primitives(**case["prof_prim_cfg"])
    cfg = case["search_space_cfg"]
    assert (
        len(primitives)
        == len(cfg["width_choice"])
        * len(cfg["kernel_choice"])
        * len(cfg["num_cell_groups"][1:])
        * 2
    )
    fields = {f for f in Prim._fields if not f == "kwargs"}
    for prim in primitives:
        assert isinstance(prim, dict)
        assert fields.issubset(prim.keys())
    base_cfg = {"final_model_cfg": {}}
    nets = assemble_profiling_nets(primitives, base_cfg, image_size=224)
    gss = GeneralSearchSpace([])
    counts = 0
    for net in nets:
        genotype = net["final_model_cfg"]["genotypes"]
        assert isinstance(genotype, (list, str))
        if isinstance(genotype, str):
            genotype = genotype_from_str(genotype, gss)
        counts += len(genotype)
        is_channel_consist = [
            c["C_out"] == n["C"] for c, n in zip(genotype[:-1], genotype[1:])
        ]
        assert all(is_channel_consist)

        spatial_size = [g["spatial_size"] for g in genotype]
        stride = [g["stride"] for g in genotype]
        is_size_consist = [
            round(c_size / s) == n_size
            for s, c_size, n_size in zip(stride, spatial_size[:-1], spatial_size[1:])
        ]
        assert all(is_size_consist)

    assert counts >= len(primitives)


@pytest.mark.parametrize(
    "case",
    [
        {
            "search_space_cfg": {
                "width_choice": [3, 4, 6],
                "depth_choice": [2, 3, 4],
                "kernel_choice": [3, 5, 7],
                "num_cell_groups": [1, 4, 4, 4, 4, 4],
                "expansions": [1, 6, 6, 6, 6, 6],
            },
            "prof_prim_cfg": {
                "spatial_size": 112,
                "base_channels": [16, 16, 24, 32, 64, 96, 160, 320, 1280],
                "mult_ratio": 1.0,
                "strides": [1, 2, 2, 2, 1, 2],
                "activation": ["relu", "relu", "relu", "h_swish", "h_swish", "h_swish"],
                "use_se": [False, False, True, False, True, True],
                "primitive_type": "mobilenet_v3_block",
                "performances": ["latency",],
            },
            "hwobjmodel_type": "ofa",
            "hwobjmodel_cfg": {},
            "prof_prim_latencies": [
                {
                    "prim_type": "mobilenet_v3_block",
                    "C": 16,
                    "C_out": 24,
                    "spatial_size": 112,
                    "expansion": 4,
                    "use_se": True,
                    "stride": 2,
                    "kernel_size": 3,
                    "activation": "relu",
                    "latency": 12.5,
                },
            ],
        }
    ],
)
def test_gen_model(case):
    from aw_nas.common import get_search_space
    from aw_nas.hardware.base import MixinProfilingSearchSpace
    from aw_nas.hardware.utils import Prim

    ss = get_search_space("ofa_mixin", **case["search_space_cfg"])
    assert isinstance(ss, MixinProfilingSearchSpace)

    prof_prim_latencies = case["prof_prim_latencies"]

    hwobj_model = ss.parse_profiling_primitives(
        prof_prim_latencies, case["prof_prim_cfg"], case["hwobjmodel_cfg"]
    )

    for prim, perf in hwobj_model._table.items():
        assert isinstance(prim, Prim)
        assert isinstance(perf, hwobj_model.Perf)
        assert len(perf) == len(case["prof_prim_cfg"]["performances"])