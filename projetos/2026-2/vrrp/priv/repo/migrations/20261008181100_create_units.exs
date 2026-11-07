defmodule Tcc.Repo.Migrations.CreateUnits do
  use Ecto.Migration

  def change do
    create table(:units, primary_key: false) do
      add :name, :string, primary_key: true
      add :description, :string
      add :symbol, :string
    end
  end
end
