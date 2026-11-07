defmodule Tcc.SensorsFixtures do
  @moduledoc """
  This module defines test helpers for creating
  entities via the `Tcc.Sensors` context.
  """

  @doc """
  Generate a sensor.
  """
  def sensor_fixture(attrs \\ %{}) do
    {:ok, sensor} =
      attrs
      |> Enum.into(%{
        module: "some module",
        timestamp: ~U[2026-10-07 02:32:00.000000Z],
        unit: "some unit",
        value: "120.5"
      })
      |> Tcc.Sensors.create_sensor()

    sensor
  end
end
