defmodule Tcc.Repo.Migrations.CreateDevices do
  use Ecto.Migration

  def change do
    create table(:devices, primary_key: false) do
      add :id, :binary_id, primary_key: true
      add :name, :string, null: false
      add :external_id, :string
      add :location, :string

      timestamps(type: :utc_datetime)
    end

    create unique_index(:devices, [:external_id])
  end
end
