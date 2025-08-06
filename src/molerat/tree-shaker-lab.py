import ast
from dataclasses import dataclass, field
from typing import Optional, List
import os
import pprint

@dataclass
class ModuleImports:
    functional_identifier: str
    import_name: str
    module_name: str
    level: Optional[int] = field(default=0)
    # relative_path: str
    # absolute_path: str


def get_local_modules(path: str):
    local_modules: List[str] = []
    directories = [dirent.name for dirent in os.scandir(path) if dirent.is_dir()]
    for directory in directories:
        files = [dirent.name for dirent in os.scandir(os.path.join(path,directory)) if dirent.is_file()]

        if "__init__.py" in files:
            local_modules.append(directory)

    return local_modules

def resolve_wildcard_imports(module_path: str):
    with open(module_path,"r", encoding="utf-8") as f:
        source = f.read()
        tree = ast.parse(source,filename=module_path)

        indentifiers = set[str]()

        for node in tree.body:
            match node:
                case ast.FunctionDef(name=name):
                    indentifiers.add(name) 
                case ast.ClassDef(name=name):
                    indentifiers.add(name)
                case ast.Assign(targets=targets):
                    for target in targets:
                        match target:
                            case ast.Name(id=varname):
                                indentifiers.add(varname)
                case ast.AnnAssign(target=ast.Name(id=varname)):
                    indentifiers.add(varname)
                case _:
                    pass

        return list(indentifiers)


class LocalImportVisitor(ast.NodeVisitor):

    def __init__(self, path: str, relative_path: str):
        self.imports: List[ModuleImports] = []
        self.path = path
        self.relative_path = relative_path
        self.local_modules = []
        self.lvl2_local_modules = []
        self.init_local_modules()

    def init_local_modules(self):
        if len(self.local_modules) == 0:
            path = self.path
            if os.path.isfile(path):
                path = os.path.join(*path.split(os.path.sep)[:-1])
                if os.path.sep == "/":
                    path = "/" + path
                self.local_modules = get_local_modules(path)
        
        if len(self.lvl2_local_modules) == 0:
            path = self.path
            if os.path.isfile(path):
                path_parts = path.split(os.path.sep)[:-2]
            else:
                path_parts = path.split(os.path.sep)[:-1]

            path = os.path.join(*path_parts)
            
            if os.path.sep == "/":
                path = "/" + path

            self.lvl2_local_modules = get_local_modules(path)

    def visit_Import(self, node: ast.Import):

       
        for alias in node.names:
            directory_name = alias.name.split(".")[0]

            if directory_name in self.local_modules:
                functional_identifier = alias.asname if alias.asname else alias.name
                
                self.imports.append(ModuleImports(
                    functional_identifier=functional_identifier,
                    import_name=alias.name,
                    module_name=alias.name
                ))

        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):

        for alias in node.names:
            if node.level == 2:
                directory_name = node.module.split(".")[0]
            else:
                directory_name = node.module.split(".")[0]
            
            print(f"import level : {node.level}, name={alias.name}")
            print("lvl2_local_modules = ",self.lvl2_local_modules)

            if (directory_name in self.local_modules and node.level == 0) or  (directory_name in self.lvl2_local_modules and node.level == 2):
                functional_identifier = alias.asname if alias.asname else alias.name
                
                if functional_identifier != "*":
                    self.imports.append(ModuleImports(
                        functional_identifier=functional_identifier,
                        import_name=alias.name,
                        level=node.level,
                        module_name=node.module
                    ))
                else:
                    base_path = self.path

                    if os.path.isfile(base_path):
                        base_path = os.path.join(*base_path.split("/")[:-1])
                    
                    if node.level == 2:
                        base_path = os.path.join(*base_path.split("/")[:-1])
                    
                    if os.path.sep == "/":
                        base_path = "/" + base_path

                    print(f"node.level = {node.level}, path={self.path} {base_path=}")


                    if len(node.module.split(".")) > 0:
                        module_path = os.path.join(*node.module.split(".")) + ".py"
                    
                    else:
                        module_path = f"{alias}/__init__.py"


                    file_path = os.path.join(base_path,module_path)

                    print(f"{file_path=}")
                    
                    if not os.path.exists(file_path):
                        continue

                    imports = resolve_wildcard_imports(file_path)

                    print(f"Wildcard imports for module_path = {file_path} are: ",imports)

                    for _import in imports:
                        self.imports.append(ModuleImports(
                            functional_identifier=_import,
                            import_name=_import,
                            module_name=node.module,
                            level=node.level
                        ))

        self.generic_visit(node)

    def get_local_imports(self):
        with open(self.path,"r",encoding="utf-8") as f:
            source = f.read()
            tree = ast.parse(source)
            # print("\n\nTree Dum\n\n")
            # print(ast.dump(tree, indent=1))
            # print("\n\n")
            self.visit(tree)
        return self.imports
    

    

if __name__ == "__main__":
    liv = LocalImportVisitor(os.path.join(os.getcwd(),"module_a/mod.py"),"module_a/mod.py")
    # liv.visit()
    pp = pprint.PrettyPrinter()
    pp.pprint(liv.get_local_imports())


# class MyVisitor(ast.NodeVisitor):
#     def __init__(self, file_writer):
#         self.fw = file_writer
#     def visit_Import(self, node: ast.Import):
#         self.fw.write(f"Import Node Encountered: {ast.dump(node, indent=1)}\n\n")
#         self.generic_visit(node)
#     def visit_ImportFrom(self, node: ast.ImportFrom):
#         self.fw.write(f"ImportFrom Node Encountered: {ast.dump(node,indent=1)}\n\n")
#         self.generic_visit(node)
#     def visit_FunctionDef(self, node: ast.FunctionDef):
#         self.fw.write(f"FunctionDef Node Encountered: {ast.dump(node,indent=1)}\n\n")
#         self.generic_visit(node)
#     def visit_Expr(self, node: ast.Expr):
#         self.fw.write(f"Expr Node Encountered: {ast.dump(node,indent=1)}\n\n")
#         self.generic_visit(node)
#     def visit_ClassDef(self, node: ast.ClassDef):
#         self.fw.write(f"ClassDef Node Encountered: {ast.dump(node,indent=1)}\n\n")
#         self.generic_visit(node)
#     def visit_Assign(self, node):
#         self.fw.write(f"Assign Node Encountered: {ast.dump(node,indent=1)}\n\n")
#         self.generic_visit(node)
#     def visit_Call(self, node):
#         self.fw.write(f"Call Node Encountered: {ast.dump(node, indent=1)}\n\n")
