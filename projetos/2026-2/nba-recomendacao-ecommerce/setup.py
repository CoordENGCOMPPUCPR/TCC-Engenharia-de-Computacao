import setuptools

setuptools.setup(
    name="tcc-nba",
    version="1.0",
    packages=setuptools.find_packages(),
    python_requires=">=3.9,<3.13",
    # versões do ambiente em que os artefatos e resultados foram gerados
    install_requires=[
        "lightgbm==4.6.0",
        "scikit-learn==1.6.1",
        "pandas==2.3.3",
        "numpy==2.0.2",
        "scipy==1.13.1",
        "shap==0.49.1",
        "numba==0.60.0",
        "pyarrow==21.0.0",
        "mlxtend==0.23.4",
        "fastapi==0.128.8",
        "uvicorn==0.39.0",
        "optuna==4.9.0",
        "matplotlib==3.9.4",
    ],
    extras_require={
        "test": ["pytest==8.4.2", "httpx==0.28.1"],
    },
)
