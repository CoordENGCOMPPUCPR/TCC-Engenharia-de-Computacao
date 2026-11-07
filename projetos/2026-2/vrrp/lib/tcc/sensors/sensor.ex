defmodule Tcc.Sensors.Sensor do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, :binary_id, autogenerate: true}
  @foreign_key_type :binary_id
  schema "sensors" do
    field :module, :string
    field :external_id, :string

    belongs_to :device, Tcc.Devices.Device
    has_many :values, Tcc.Sensors.SensorValue

    timestamps(type: :utc_datetime)
  end

  @doc false
  def changeset(sensor, attrs) do
    sensor
    |> cast(attrs, [:module, :external_id, :device_id])
    |> validate_required([:module, :external_id, :device_id])
    |> foreign_key_constraint(:device_id)
    |> unique_constraint(:external_id)
  end
end
