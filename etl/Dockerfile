FROM debian:bookworm-slim as development
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Conda
ENV CONDA_DIR=/opt/conda
RUN curl -L https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh \
    -o /tmp/miniforge.sh \
 && bash /tmp/miniforge.sh -b -p $CONDA_DIR \
 && rm /tmp/miniforge.sh
ENV PATH=$CONDA_DIR/bin:$PATH
COPY environment.yml /app/environment.yml
RUN conda env create -f /app/environment.yml
ENV CONDA_DEFAULT_ENV=etl
ENV PATH=$CONDA_DIR/envs/etl/bin:$PATH

WORKDIR /app
COPY ./etl ./etl
CMD ["python", "-m", "etl.main"]