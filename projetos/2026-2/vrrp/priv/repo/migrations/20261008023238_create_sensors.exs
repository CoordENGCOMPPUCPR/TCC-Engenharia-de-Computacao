defmodule Tcc.Repo.Migrations.CreateSensors do
  use Ecto.Migration

  def change do
    create table(:sensors, primary_key: false) do
      add :id, :binary_id, primary_key: true
      add :external_id, :string
      add :module, :string

      add :device_id, references(:devices, type: :binary_id, on_delete: :delete_all)
      timestamps(type: :utc_datetime)
    end

    create index(:sensors, [:device_id, :module])
    create unique_index(:sensors, [:external_id])
  end
end
