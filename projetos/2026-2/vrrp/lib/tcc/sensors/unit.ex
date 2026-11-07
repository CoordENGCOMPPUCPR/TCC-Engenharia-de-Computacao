defmodule Tcc.Sensors.Unit do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:name, :string, []}
  schema "units" do
    field :description, :string
    field :symbol, :string
  end

  @doc false
  def changeset(unit, attrs) do
    unit
    |> cast(attrs, [:name, :description, :symbol])
    |> update_change(:name, &String.downcase/1)
    |> validate_required([:name, :symbol])
    |> unique_constraint(:name, name: :units_pkey)
  end
end
