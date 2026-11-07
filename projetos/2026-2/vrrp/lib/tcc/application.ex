defmodule Tcc.Application do
  # See https://elixir.hexdocs.pm/Application.html
  # for more information on OTP Applications
  @moduledoc false

  use Application

  @impl true
  def start(_type, _args) do
    children = [
      TccWeb.Telemetry,
      Tcc.Repo,
      {DNSCluster, query: Application.get_env(:tcc, :dns_cluster_query) || :ignore},
      {Phoenix.PubSub, name: Tcc.PubSub},
      # Start a worker by calling: Tcc.Worker.start_link(arg)
      # {Tcc.Worker, arg},
      # Start to serve requests, typically the last entry
      TccWeb.Endpoint
    ]

    # See https://elixir.hexdocs.pm/Supervisor.html
    # for other strategies and supported options
    opts = [strategy: :one_for_one, name: Tcc.Supervisor]
    Supervisor.start_link(children, opts)
  end

  # Tell Phoenix to update the endpoint configuration
  # whenever the application is updated.
  @impl true
  def config_change(changed, _new, removed) do
    TccWeb.Endpoint.config_change(changed, removed)
    :ok
  end
end
