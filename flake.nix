{
  description = "Development environment for the systems-engineering spec toolkit";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-26.05";
  };

  outputs =
    { self, nixpkgs }:
    let
      supportedSystems = [ "x86_64-linux" ];
      forAllSystems = f: nixpkgs.lib.genAttrs supportedSystems (system: f system);
    in
    {
      devShells = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python3.withPackages (ps: [
            ps.pyyaml
            ps.pytest
          ]);
        in
        {
          default = pkgs.mkShell {
            name = "syseng-dev";
            packages = [ python ];
            # Run the CLI from source: `spec check`, `spec render`, ...
            shellHook = ''
              export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
              export PATH="$PWD/bin:$PATH"
            '';
          };
        }
      );
    };
}
