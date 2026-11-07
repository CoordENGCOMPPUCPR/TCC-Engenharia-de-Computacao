defmodule Tcc.DevicesFixtures do
  @moduledoc """
  This module defines test helpers for creating
  entities via the `Tcc.Devices` context.
  """

  @doc """
  Generate a device.
  """
  def device_fixture(attrs \\ %{}) do
    {:ok, device} =
      attrs
      |> Enum.into(%{
        localtion: "some localtion",
        name: "some name"
      })
      |> Tcc.Devices.create_device()

    device
  end
end
