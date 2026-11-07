defmodule Tcc.Repo.Migrations.CreateSensorValues do
  use Ecto.Migration

  def change do
    create table(:sensor_values, primary_key: false) do
      add :sensor_id, references(:sensors, type: :binary_id, on_delete: :delete_all),
        primary_key: true,
        null: false

      add :timestamp, :utc_datetime, primary_key: true, null: false

      add :unit_name, references(:units, column: :name, type: :string, on_delete: :restrict),
        primary_key: true,
        null: false

      add :value, :decimal, null: false
      timestamps(type: :utc_datetime)
    end

    create index(:sensor_values, [:unit_name, :sensor_id, :timestamp])
  end
end
