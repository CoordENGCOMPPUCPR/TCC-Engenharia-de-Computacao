defmodule Tcc.Sensors.SensorValue do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key false
  schema "sensor_values" do
    field :timestamp, :utc_datetime, primary_key: true
    field :value, :decimal

    belongs_to :sensor, Tcc.Sensors.Sensor, type: :binary_id, primary_key: true

    belongs_to :unit, Tcc.Sensors.Unit,
      foreign_key: :unit_name,
      references: :name,
      type: :string,
      primary_key: true

    timestamps(type: :utc_datetime)
  end

  @doc false
  def changeset(sensor_value, attrs) do
    sensor_value
    |> cast(attrs, [:timestamp, :value, :sensor_id, :unit_name])
    |> validate_required([:timestamp, :value, :sensor_id, :unit_name])
    |> foreign_key_constraint(:sensor_id)
    |> foreign_key_constraint(:unit_name)
  end
end
