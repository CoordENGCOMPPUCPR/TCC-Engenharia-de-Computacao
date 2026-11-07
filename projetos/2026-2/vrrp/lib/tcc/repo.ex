defmodule Tcc.Repo do
  use Ecto.Repo,
    otp_app: :tcc,
    adapter: Ecto.Adapters.Postgres
end
