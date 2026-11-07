defmodule Tcc.Devices.Device do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, :binary_id, autogenerate: true}
  @foreign_key_type :binary_id
  schema "devices" do
    field :name, :string
    field :location, :string
    field :external_id, :string

    has_many :sensors, Tcc.Sensors.Sensor
    timestamps(type: :utc_datetime)
  end

  @doc false
  def changeset(device, attrs) do
    device
    |> cast(attrs, [:name, :external_id, :location])
    |> validate_required([:name, :external_id, :location])
  end
end
