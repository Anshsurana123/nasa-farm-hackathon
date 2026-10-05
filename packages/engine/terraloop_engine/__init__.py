"""TerraLoop decision engine.

Layout (see AGENTS.md for rules):
    data/      external data clients (NASA POWER, SoilGrids, GEE, Earthdata)
    eo/        Earth-observation analytics (phenology, crop-history inference)
    models/    process models (soil, agroclimate, RUSLE, RothC, AquaCrop, N-balance)
    climate/   historical + CMIP6 scenario ensembles
    optimize/  rotation generation, NSGA-II, priority-based selection
    explain/   why-cards and LLM tool definitions
    crop_kb.py crop knowledge base loader
    profiler.py builds a FieldProfile for a location
"""

__version__ = "0.1.0"
